//! High-performance semantic chunker with UAX#29 sentence boundaries and
//! `rayon` page-level parallelism.

use rayon::prelude::*;
use unicode_segmentation::UnicodeSegmentation;
use uuid::Uuid;

pub const DEFAULT_TARGET_TOKENS: usize = 800;
pub const DEFAULT_OVERLAP_TOKENS: usize = 100;
pub const DEFAULT_MIN_TOKENS: usize = 150;
const WORD_TO_TOKEN_RATIO: f64 = 1.33;

const CHUNK_NAMESPACE: Uuid = Uuid::from_bytes([
    0x9a, 0x1b, 0x7c, 0x3e, 0x2f, 0x4d, 0x4a, 0x6b, 0x8c, 0x9d, 0x0e, 0x1f, 0x2a, 0x3b, 0x4c, 0x5d,
]);

#[derive(Debug, Clone)]
pub struct PageInput {
    pub page_number: Option<i64>,
    pub text: String,
    pub section: Option<String>,
}

#[derive(Debug, Clone)]
pub struct ChunkOutput {
    pub chunk_id: String,
    pub source_id: String,
    pub notebook_id: String,
    pub text: String,
    pub token_count: usize,
    pub page: Option<i64>,
    pub section: Option<String>,
    pub start_char: usize,
    pub end_char: usize,
    pub embedding_model: String,
}

pub fn deterministic_chunk_id(source_id: &str, start_char: usize, text: &str) -> String {
    let input = format!("{source_id}:{start_char}:{text}");
    Uuid::new_v5(&CHUNK_NAMESPACE, input.as_bytes()).to_string()
}

#[inline]
pub fn estimate_tokens(text: &str) -> usize {
    if text.is_empty() {
        return 0;
    }
    let word_count = text.split_whitespace().count();
    ((word_count as f64) * WORD_TO_TOKEN_RATIO) as usize
}

fn split_paragraphs(text: &str) -> Vec<&str> {
    let mut paragraphs = Vec::new();
    let mut start = 0usize;
    let bytes = text.as_bytes();
    let len = bytes.len();
    let mut i = 0usize;

    while i < len {
        if bytes[i] == b'\n' {
            let mut j = i + 1;
            while j < len && (bytes[j] == b' ' || bytes[j] == b'\t' || bytes[j] == b'\r') {
                j += 1;
            }
            if j < len && bytes[j] == b'\n' {
                let slice = text[start..i].trim();
                if !slice.is_empty() {
                    paragraphs.push(slice);
                }
                while j < len
                    && (bytes[j] == b'\n'
                        || bytes[j] == b' '
                        || bytes[j] == b'\t'
                        || bytes[j] == b'\r')
                {
                    j += 1;
                }
                start = j;
                i = j;
                continue;
            }
        }
        i += 1;
    }

    if start < len {
        let tail = text[start..].trim();
        if !tail.is_empty() {
            paragraphs.push(tail);
        }
    }
    paragraphs
}

fn split_sentences_uax29(text: &str) -> Vec<&str> {
    text.unicode_sentences()
        .map(str::trim)
        .filter(|s| !s.is_empty())
        .collect()
}

fn split_by_tokens(text: &str, max_tokens: usize) -> Vec<String> {
    let words: Vec<&str> = text.split_whitespace().collect();
    let max_words = ((max_tokens as f64) / WORD_TO_TOKEN_RATIO).floor() as usize;
    let step = max_words.max(1);
    words.chunks(step).map(|w| w.join(" ")).collect()
}

fn make_chunk(
    parts: &[String],
    source_id: &str,
    notebook_id: &str,
    page: Option<i64>,
    section: Option<&str>,
    embedding_model: &str,
    start_char: usize,
) -> ChunkOutput {
    let text = parts.join("\n\n");
    let token_count = estimate_tokens(&text);
    let end_char = start_char + text.len();
    ChunkOutput {
        chunk_id: deterministic_chunk_id(source_id, start_char, &text),
        source_id: source_id.to_string(),
        notebook_id: notebook_id.to_string(),
        text,
        token_count,
        page,
        section: section.map(str::to_string),
        start_char,
        end_char,
        embedding_model: embedding_model.to_string(),
    }
}

pub fn chunk_single_page(
    page_input: &PageInput,
    source_id: &str,
    notebook_id: &str,
    embedding_model: &str,
    target_tokens: usize,
) -> Vec<ChunkOutput> {
    if page_input.text.trim().is_empty() {
        return Vec::new();
    }

    let paragraphs = split_paragraphs(&page_input.text);
    let mut chunks = Vec::new();
    let mut current_parts: Vec<String> = Vec::new();
    let mut current_tokens = 0usize;
    let mut char_offset = 0usize;
    let section_ref = page_input.section.as_deref();

    for para in paragraphs {
        let para_tokens = estimate_tokens(para);
        if para_tokens > target_tokens {
            if !current_parts.is_empty() {
                chunks.push(make_chunk(
                    &current_parts,
                    source_id,
                    notebook_id,
                    page_input.page_number,
                    section_ref,
                    embedding_model,
                    char_offset,
                ));
                char_offset += current_parts.iter().map(|p| p.len() + 2).sum::<usize>();
                current_parts.clear();
                current_tokens = 0;
            }

            let sentences = split_sentences_uax29(para);
            let mut sent_parts: Vec<String> = Vec::new();
            let mut sent_tokens = 0usize;

            for sent in sentences {
                let st = estimate_tokens(sent);
                if st > target_tokens {
                    if !sent_parts.is_empty() {
                        chunks.push(make_chunk(
                            &sent_parts,
                            source_id,
                            notebook_id,
                            page_input.page_number,
                            section_ref,
                            embedding_model,
                            char_offset,
                        ));
                        char_offset += sent_parts.iter().map(|s| s.len() + 1).sum::<usize>();
                        sent_parts.clear();
                        sent_tokens = 0;
                    }
                    for tc in split_by_tokens(sent, target_tokens) {
                        let tc_len = tc.len();
                        chunks.push(make_chunk(
                            &[tc],
                            source_id,
                            notebook_id,
                            page_input.page_number,
                            section_ref,
                            embedding_model,
                            char_offset,
                        ));
                        char_offset += tc_len + 1;
                    }
                } else if sent_tokens + st > target_tokens {
                    if !sent_parts.is_empty() {
                        chunks.push(make_chunk(
                            &sent_parts,
                            source_id,
                            notebook_id,
                            page_input.page_number,
                            section_ref,
                            embedding_model,
                            char_offset,
                        ));
                        char_offset += sent_parts.iter().map(|s| s.len() + 1).sum::<usize>();
                    }
                    sent_parts = vec![sent.to_string()];
                    sent_tokens = st;
                } else {
                    sent_parts.push(sent.to_string());
                    sent_tokens += st;
                }
            }

            if !sent_parts.is_empty() {
                chunks.push(make_chunk(
                    &sent_parts,
                    source_id,
                    notebook_id,
                    page_input.page_number,
                    section_ref,
                    embedding_model,
                    char_offset,
                ));
                char_offset += sent_parts.iter().map(|s| s.len() + 1).sum::<usize>();
            }
        } else if current_tokens + para_tokens > target_tokens {
            if !current_parts.is_empty() {
                chunks.push(make_chunk(
                    &current_parts,
                    source_id,
                    notebook_id,
                    page_input.page_number,
                    section_ref,
                    embedding_model,
                    char_offset,
                ));
                char_offset += current_parts.iter().map(|p| p.len() + 2).sum::<usize>();
            }
            current_parts = vec![para.to_string()];
            current_tokens = para_tokens;
        } else {
            current_parts.push(para.to_string());
            current_tokens += para_tokens;
        }
    }

    if !current_parts.is_empty() {
        chunks.push(make_chunk(
            &current_parts,
            source_id,
            notebook_id,
            page_input.page_number,
            section_ref,
            embedding_model,
            char_offset,
        ));
    }

    chunks
}

pub fn chunk_pages_parallel(
    pages: &[PageInput],
    source_id: &str,
    notebook_id: &str,
    embedding_model: &str,
    target_tokens: usize,
    overlap_tokens: usize,
    min_tokens: usize,
) -> Vec<ChunkOutput> {
    let raw_chunks: Vec<ChunkOutput> = pages
        .par_iter()
        .flat_map_iter(|page| {
            chunk_single_page(page, source_id, notebook_id, embedding_model, target_tokens)
        })
        .collect();

    let overlapped = apply_overlap(raw_chunks, overlap_tokens);
    consolidate_small_chunks(overlapped, min_tokens)
}

fn apply_overlap(chunks: Vec<ChunkOutput>, overlap_tokens: usize) -> Vec<ChunkOutput> {
    if chunks.len() <= 1 || overlap_tokens == 0 {
        return chunks;
    }
    let overlap_words = ((overlap_tokens as f64) / WORD_TO_TOKEN_RATIO).floor() as usize;
    let mut result = Vec::with_capacity(chunks.len());
    result.push(chunks[0].clone());

    for i in 1..chunks.len() {
        let prev_words: Vec<&str> = chunks[i - 1].text.split_whitespace().collect();
        let start_idx = prev_words.len().saturating_sub(overlap_words);
        let overlap_text = prev_words[start_idx..].join(" ");
        let new_text = format!("{overlap_text}\n\n{}", chunks[i].text);
        let mut updated = chunks[i].clone();
        updated.token_count = estimate_tokens(&new_text);
        updated.text = new_text;
        result.push(updated);
    }
    result
}

fn consolidate_small_chunks(chunks: Vec<ChunkOutput>, min_tokens: usize) -> Vec<ChunkOutput> {
    if chunks.is_empty() {
        return Vec::new();
    }
    if chunks.len() == 1 {
        return if chunks[0].text.trim().is_empty() {
            Vec::new()
        } else {
            chunks
        };
    }

    let mut consolidated: Vec<ChunkOutput> = Vec::with_capacity(chunks.len());
    for chunk in chunks {
        if chunk.text.trim().is_empty() {
            continue;
        }
        if chunk.token_count < min_tokens {
            if let Some(prev) = consolidated.last_mut() {
                prev.text = format!("{}\n\n{}", prev.text, chunk.text);
                prev.token_count = estimate_tokens(&prev.text);
                prev.end_char = prev.end_char.max(chunk.end_char);
                continue;
            }
        }
        consolidated.push(chunk);
    }
    consolidated
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_deterministic_chunk_id_matches_uuid_v5() {
        let id1 = deterministic_chunk_id("src-1", 0, "hello world");
        let id2 = deterministic_chunk_id("src-1", 0, "hello world");
        assert_eq!(id1, id2);
        assert_eq!(id1.len(), 36);
    }

    #[test]
    fn test_chunk_pages_parallel_preserves_pages_and_consolidates() {
        let pages = vec![
            PageInput {
                page_number: Some(1),
                text: "First paragraph about Google Cloud Storage.".to_string(),
                section: Some("Intro".to_string()),
            },
            PageInput {
                page_number: Some(2),
                text: "Second paragraph about PostgreSQL pgvector indexing.".to_string(),
                section: Some("Storage".to_string()),
            },
        ];
        let chunks = chunk_pages_parallel(
            &pages,
            "source-123",
            "notebook-456",
            "text-embedding-004",
            DEFAULT_TARGET_TOKENS,
            DEFAULT_OVERLAP_TOKENS,
            DEFAULT_MIN_TOKENS,
        );
        assert_eq!(chunks.len(), 1);
        assert!(chunks[0].text.contains("Google Cloud Storage"));
        assert!(chunks[0].text.contains("PostgreSQL pgvector"));
    }
}
