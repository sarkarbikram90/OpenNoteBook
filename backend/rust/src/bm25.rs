//! Pre-computed BM25 Okapi Inverted Index.
//!
//! Eliminates the per-query `BM25Okapi(tokenised_corpus)` rebuild in Python by
//! pre-computing posting lists, document lengths, and IDF weights at index time
//! and evaluating queries in O(query_terms * posting_list_len).

use serde::{Deserialize, Serialize};
use std::collections::HashMap;

const BM25_K1: f64 = 1.5;
const BM25_B: f64 = 0.75;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Bm25InvertedIndex {
    pub chunk_ids: Vec<String>,
    pub doc_lengths: Vec<u32>,
    pub avgdl: f64,
    pub idf: HashMap<String, f64>,
    pub postings: HashMap<String, Vec<(u32, u32)>>,
}

pub fn tokenize(text: &str) -> Vec<String> {
    text.split(|c: char| !c.is_alphanumeric())
        .filter(|tok| !tok.is_empty())
        .map(|tok| stem_light(&tok.to_ascii_lowercase()))
        .collect()
}

fn stem_light(word: &str) -> String {
    if word.len() <= 4 {
        return word.to_string();
    }
    for suffix in ["ingly", "edly", "ing", "ed", "ies", "es", "s"] {
        if let Some(stripped) = word.strip_suffix(suffix) {
            if stripped.len() >= 3 {
                if suffix == "ies" {
                    return format!("{stripped}y");
                }
                return stripped.to_string();
            }
        }
    }
    word.to_string()
}

impl Bm25InvertedIndex {
    pub fn build(chunk_ids: Vec<String>, texts: &[String]) -> Self {
        let num_docs = chunk_ids.len();
        if num_docs == 0 || texts.is_empty() {
            return Self {
                chunk_ids: Vec::new(),
                doc_lengths: Vec::new(),
                avgdl: 0.0,
                idf: HashMap::new(),
                postings: HashMap::new(),
            };
        }

        let mut doc_lengths = Vec::with_capacity(num_docs);
        let mut postings: HashMap<String, Vec<(u32, u32)>> = HashMap::new();
        let mut total_len = 0u64;

        for (doc_idx, text) in texts.iter().take(num_docs).enumerate() {
            let tokens = tokenize(text);
            let doc_len = tokens.len() as u32;
            doc_lengths.push(doc_len);
            total_len += doc_len as u64;

            let mut term_freqs: HashMap<String, u32> = HashMap::new();
            for tok in tokens {
                *term_freqs.entry(tok).or_insert(0) += 1;
            }
            for (term, freq) in term_freqs {
                postings
                    .entry(term)
                    .or_default()
                    .push((doc_idx as u32, freq));
            }
        }

        let avgdl = if num_docs > 0 {
            (total_len as f64) / (num_docs as f64)
        } else {
            0.0
        };

        let n = num_docs as f64;
        let mut idf = HashMap::with_capacity(postings.len());
        for (term, plist) in &postings {
            let df = plist.len() as f64;
            let score = ((n - df + 0.5) / (df + 0.5) + 1.0).ln();
            idf.insert(term.clone(), score);
        }

        Self {
            chunk_ids,
            doc_lengths,
            avgdl,
            idf,
            postings,
        }
    }

    pub fn score_query(&self, query: &str, top_k: usize) -> Vec<(String, f64)> {
        if self.chunk_ids.is_empty() || self.avgdl <= 0.0 || top_k == 0 {
            return Vec::new();
        }

        let query_terms = tokenize(query);
        if query_terms.is_empty() {
            return Vec::new();
        }

        let mut doc_scores: HashMap<u32, f64> = HashMap::new();
        for term in query_terms {
            let Some(&term_idf) = self.idf.get(&term) else {
                continue;
            };
            if term_idf <= 0.0 {
                continue;
            }
            let Some(plist) = self.postings.get(&term) else {
                continue;
            };
            for &(doc_idx, tf) in plist {
                let dl = *self.doc_lengths.get(doc_idx as usize).unwrap_or(&0) as f64;
                let tf_f = tf as f64;
                let denom = tf_f + BM25_K1 * (1.0 - BM25_B + BM25_B * (dl / self.avgdl));
                let term_score = term_idf * ((tf_f * (BM25_K1 + 1.0)) / denom);
                *doc_scores.entry(doc_idx).or_insert(0.0) += term_score;
            }
        }

        let mut scored: Vec<(String, f64)> = doc_scores
            .into_iter()
            .filter(|&(_, score)| score > 0.0)
            .filter_map(|(doc_idx, score)| {
                self.chunk_ids
                    .get(doc_idx as usize)
                    .map(|cid| (cid.clone(), score))
            })
            .collect();

        scored.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap_or(std::cmp::Ordering::Equal));
        scored.truncate(top_k);
        scored
    }

    pub fn to_json(&self) -> Result<String, serde_json::Error> {
        serde_json::to_string(self)
    }

    pub fn from_json(json_str: &str) -> Result<Self, serde_json::Error> {
        serde_json::from_str(json_str)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_bm25_inverted_index_ranks_relevant_chunks_first() {
        let chunk_ids = vec![
            "chunk-1".to_string(),
            "chunk-2".to_string(),
            "chunk-3".to_string(),
        ];
        let texts = vec![
            "Google Cloud Storage emits OBJECT_FINALIZE notifications to Pub/Sub.".to_string(),
            "PostgreSQL pgvector stores high-dimensional embedding vectors.".to_string(),
            "Tesseract OCR extracts text from uploaded raster images.".to_string(),
        ];

        let index = Bm25InvertedIndex::build(chunk_ids, &texts);
        let serialized = index.to_json().expect("serialize index");
        let restored = Bm25InvertedIndex::from_json(&serialized).expect("deserialize index");

        let hits = restored.score_query("Cloud Storage OBJECT_FINALIZE Pub/Sub", 2);
        assert!(!hits.is_empty());
        assert_eq!(hits[0].0, "chunk-1");
        assert!(hits[0].1 > 0.0);
    }
}
