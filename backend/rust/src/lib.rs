//! `opennotebook_core` — Rust data-plane accelerator for OpenNotebook.
//!
//! Exposes both pure-Rust modules (`pii`, `chunker`, `bm25`) and, when compiled
//! with `--features python`, the `PyO3` native extension module `opennotebook_core`
//! that releases the Python GIL (`py.allow_threads`) during CPU-intensive work.

pub mod bm25;
pub mod chunker;
pub mod pii;

#[cfg(feature = "python")]
mod py_bindings {
    use crate::bm25::Bm25InvertedIndex;
    use crate::chunker::{chunk_pages_parallel, PageInput};
    use crate::pii::{scrub_text, MaskingStrategy};
    use pyo3::exceptions::PyValueError;
    use pyo3::prelude::*;
    use std::collections::HashMap;

    #[pyfunction]
    #[pyo3(signature = (text, strategy = "redact"))]
    fn scrub_pii(
        py: Python<'_>,
        text: &str,
        strategy: &str,
    ) -> PyResult<(String, HashMap<String, usize>, usize)> {
        let strat = MaskingStrategy::from_str_lossy(strategy);
        let output = py.allow_threads(|| scrub_text(text, strat));
        Ok((
            output.cleaned_text,
            output.entities_found,
            output.total_redacted,
        ))
    }

    #[pyfunction]
    #[pyo3(signature = (
        source_id,
        notebook_id,
        embedding_model,
        pages,
        target_tokens = 800,
        overlap_tokens = 100,
        min_tokens = 150
    ))]
    #[allow(clippy::too_many_arguments)]
    fn chunk_pages(
        py: Python<'_>,
        source_id: &str,
        notebook_id: &str,
        embedding_model: &str,
        pages: Vec<(Option<i64>, String, Option<String>)>,
        target_tokens: usize,
        overlap_tokens: usize,
        min_tokens: usize,
    ) -> PyResult<Vec<HashMap<String, PyObject>>> {
        let page_inputs: Vec<PageInput> = pages
            .into_iter()
            .map(|(page_number, text, section)| PageInput {
                page_number,
                text,
                section,
            })
            .collect();

        let chunks = py.allow_threads(|| {
            chunk_pages_parallel(
                &page_inputs,
                source_id,
                notebook_id,
                embedding_model,
                target_tokens,
                overlap_tokens,
                min_tokens,
            )
        });

        let mut out = Vec::with_capacity(chunks.len());
        for c in chunks {
            let mut map: HashMap<String, PyObject> = HashMap::with_capacity(10);
            map.insert(
                "chunk_id".to_string(),
                c.chunk_id.into_pyobject(py)?.unbind().into(),
            );
            map.insert(
                "source_id".to_string(),
                c.source_id.into_pyobject(py)?.unbind().into(),
            );
            map.insert(
                "notebook_id".to_string(),
                c.notebook_id.into_pyobject(py)?.unbind().into(),
            );
            map.insert(
                "text".to_string(),
                c.text.into_pyobject(py)?.unbind().into(),
            );
            map.insert(
                "token_count".to_string(),
                c.token_count.into_pyobject(py)?.unbind().into(),
            );
            map.insert(
                "page".to_string(),
                c.page.into_pyobject(py)?.unbind().into(),
            );
            map.insert(
                "section".to_string(),
                c.section.into_pyobject(py)?.unbind().into(),
            );
            map.insert(
                "start_char".to_string(),
                c.start_char.into_pyobject(py)?.unbind().into(),
            );
            map.insert(
                "end_char".to_string(),
                c.end_char.into_pyobject(py)?.unbind().into(),
            );
            map.insert(
                "embedding_model".to_string(),
                c.embedding_model.into_pyobject(py)?.unbind().into(),
            );
            out.push(map);
        }
        Ok(out)
    }

    #[pyfunction]
    fn build_bm25_index_json(
        py: Python<'_>,
        chunk_ids: Vec<String>,
        texts: Vec<String>,
    ) -> PyResult<String> {
        py.allow_threads(|| {
            let index = Bm25InvertedIndex::build(chunk_ids, &texts);
            index
                .to_json()
                .map_err(|e| PyValueError::new_err(format!("BM25 serialize error: {e}")))
        })
    }

    #[pyfunction]
    #[pyo3(signature = (index_json, query, top_k = 20))]
    fn score_bm25_index_json(
        py: Python<'_>,
        index_json: &str,
        query: &str,
        top_k: usize,
    ) -> PyResult<Vec<(String, f64)>> {
        py.allow_threads(|| {
            let index = Bm25InvertedIndex::from_json_cached(index_json)
                .map_err(|e| PyValueError::new_err(format!("BM25 deserialize error: {e}")))?;
            Ok(index.score_query(query, top_k))
        })
    }

    #[pymodule]
    pub fn opennotebook_core(m: &Bound<'_, PyModule>) -> PyResult<()> {
        m.add_function(wrap_pyfunction!(scrub_pii, m)?)?;
        m.add_function(wrap_pyfunction!(chunk_pages, m)?)?;
        m.add_function(wrap_pyfunction!(build_bm25_index_json, m)?)?;
        m.add_function(wrap_pyfunction!(score_bm25_index_json, m)?)?;
        Ok(())
    }
}
