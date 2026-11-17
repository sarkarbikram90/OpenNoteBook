//! Linear-time DFA PII detection and redaction engine.
//!
//! Uses Rust's `regex` crate (automata-backed, immune to catastrophic
//! backtracking / ReDoS) and single-pass span replacement per entity class
//! without repeated `.replace()` scans over the document buffer.

use regex::Regex;
use sha2::{Digest, Sha256};
use std::collections::HashMap;
use std::sync::OnceLock;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum MaskingStrategy {
    Redact,
    Mask,
    Hash,
}

impl MaskingStrategy {
    pub fn from_str_lossy(value: &str) -> Self {
        match value.trim().to_ascii_lowercase().as_str() {
            "mask" => Self::Mask,
            "hash" => Self::Hash,
            _ => Self::Redact,
        }
    }
}

#[derive(Debug, Clone)]
pub struct PiiScrubOutput {
    pub cleaned_text: String,
    pub entities_found: HashMap<String, usize>,
    pub total_redacted: usize,
}

struct CompiledPatterns {
    private_key: Regex,
    aws_key: Regex,
    github_token: Regex,
    ssn: Regex,
    credit_card: Regex,
    email: Regex,
    phone: Regex,
}

fn patterns() -> &'static CompiledPatterns {
    static PATTERNS: OnceLock<CompiledPatterns> = OnceLock::new();
    PATTERNS.get_or_init(|| CompiledPatterns {
        private_key: Regex::new(
            r"-----BEGIN (?:RSA |EC )?PRIVATE KEY-----[\s\S]*?-----END (?:RSA |EC )?PRIVATE KEY-----",
        )
        .expect("valid private_key regex"),
        aws_key: Regex::new(r"\b(?:AKIA|ABIA|ACCA|ASIA)[0-9A-Z]{16}\b")
            .expect("valid aws_key regex"),
        github_token: Regex::new(
            r"\b(?:ghp_[a-zA-Z0-9]{36}|github_pat_[a-zA-Z0-9_]{82})\b",
        )
        .expect("valid github_token regex"),
        // Rust's regex crate guarantees O(N) time by disallowing look-around;
        // SSN area/group/serial exclusions (000, 666, 9xx, 00, 0000) are checked in `is_valid_ssn`.
        ssn: Regex::new(r"\b\d{3}[- ]?\d{2}[- ]?\d{4}\b").expect("valid ssn regex"),
        credit_card: Regex::new(r"\b(?:\d{4}[- ]?){3}\d{1,4}\b|\b\d{13,19}\b")
            .expect("valid credit_card regex"),
        email: Regex::new(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
            .expect("valid email regex"),
        phone: Regex::new(r"(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b")
            .expect("valid phone regex"),
    })
}

pub fn is_valid_ssn(candidate: &str) -> bool {
    let digits: Vec<u8> = candidate
        .bytes()
        .filter(|b| b.is_ascii_digit())
        .collect();
    if digits.len() != 9 {
        return false;
    }
    let area = &digits[0..3];
    let group = &digits[3..5];
    let serial = &digits[5..9];
    if area == b"000" || area == b"666" || area[0] == b'9' {
        return false;
    }
    if group == b"00" || serial == b"0000" {
        return false;
    }
    true
}

pub fn luhn_check(candidate: &str) -> bool {
    let digits: Vec<u32> = candidate
        .bytes()
        .filter(|b| b.is_ascii_digit())
        .map(|b| (b - b'0') as u32)
        .collect();
    if !(13..=19).contains(&digits.len()) {
        return false;
    }
    let mut checksum = 0u32;
    for (i, &d) in digits.iter().rev().enumerate() {
        if i % 2 == 1 {
            let doubled = d * 2;
            checksum += if doubled > 9 { doubled - 9 } else { doubled };
        } else {
            checksum += d;
        }
    }
    checksum.is_multiple_of(10)
}

fn mask_value(raw: &str, entity_type: &str, strategy: MaskingStrategy) -> String {
    match strategy {
        MaskingStrategy::Redact => format!("[REDACTED_{entity_type}]"),
        MaskingStrategy::Hash => {
            let mut hasher = Sha256::new();
            hasher.update(raw.as_bytes());
            let hex = format!("{:x}", hasher.finalize());
            format!("[HASH_{entity_type}_{}]", &hex[..12])
        }
        MaskingStrategy::Mask => {
            let digits: String = raw.chars().filter(|c| c.is_ascii_digit()).collect();
            if entity_type == "CREDIT_CARD" && digits.len() >= 4 {
                return format!("****-****-****-{}", &digits[digits.len() - 4..]);
            }
            if entity_type == "SSN" && digits.len() == 9 {
                return format!("***-**-{}", &digits[5..]);
            }
            if entity_type == "EMAIL" {
                if let Some((user, domain)) = raw.split_once('@') {
                    let prefix: String = user.chars().take(2).collect();
                    return format!("{prefix}***@{domain}");
                }
            }
            format!("[REDACTED_{entity_type}]")
        }
    }
}

fn replace_validated<F>(
    input: &str,
    regex: &Regex,
    entity_type: &str,
    strategy: MaskingStrategy,
    validator: F,
) -> (String, usize)
where
    F: Fn(&str) -> bool,
{
    let mut count = 0usize;
    let mut out = String::with_capacity(input.len());
    let mut last_end = 0usize;

    for mat in regex.find_iter(input) {
        let matched_str = mat.as_str();
        if validator(matched_str) {
            out.push_str(&input[last_end..mat.start()]);
            out.push_str(&mask_value(matched_str, entity_type, strategy));
            last_end = mat.end();
            count += 1;
        }
    }
    if count == 0 {
        return (input.to_string(), 0);
    }
    out.push_str(&input[last_end..]);
    (out, count)
}

pub fn scrub_text(text: &str, strategy: MaskingStrategy) -> PiiScrubOutput {
    let pats = patterns();
    let mut entities_found: HashMap<String, usize> = HashMap::new();
    let mut total_redacted = 0usize;

    let (cleaned, pk_count) =
        replace_validated(text, &pats.private_key, "PRIVATE_KEY", strategy, |_| true);
    if pk_count > 0 {
        entities_found.insert("PRIVATE_KEY".to_string(), pk_count);
        total_redacted += pk_count;
    }

    let (cleaned, aws_count) =
        replace_validated(&cleaned, &pats.aws_key, "API_KEY", strategy, |_| true);
    if aws_count > 0 {
        *entities_found.entry("API_KEY".to_string()).or_insert(0) += aws_count;
        total_redacted += aws_count;
    }

    let (cleaned, gh_count) =
        replace_validated(&cleaned, &pats.github_token, "API_KEY", strategy, |_| true);
    if gh_count > 0 {
        *entities_found.entry("API_KEY".to_string()).or_insert(0) += gh_count;
        total_redacted += gh_count;
    }

    let (cleaned, ssn_count) =
        replace_validated(&cleaned, &pats.ssn, "SSN", strategy, is_valid_ssn);
    if ssn_count > 0 {
        entities_found.insert("SSN".to_string(), ssn_count);
        total_redacted += ssn_count;
    }

    let (cleaned, cc_count) = replace_validated(
        &cleaned,
        &pats.credit_card,
        "CREDIT_CARD",
        strategy,
        luhn_check,
    );
    if cc_count > 0 {
        entities_found.insert("CREDIT_CARD".to_string(), cc_count);
        total_redacted += cc_count;
    }

    let (cleaned, email_count) =
        replace_validated(&cleaned, &pats.email, "EMAIL", strategy, |_| true);
    if email_count > 0 {
        entities_found.insert("EMAIL".to_string(), email_count);
        total_redacted += email_count;
    }

    let (cleaned, phone_count) =
        replace_validated(&cleaned, &pats.phone, "PHONE", strategy, |cand| {
            cand.bytes().filter(|b| b.is_ascii_digit()).count() >= 10
        });
    if phone_count > 0 {
        entities_found.insert("PHONE".to_string(), phone_count);
        total_redacted += phone_count;
    }

    PiiScrubOutput {
        cleaned_text: cleaned,
        entities_found,
        total_redacted,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_ssn_and_email_redaction() {
        let raw = "Contact alice@example.com or SSN 123-45-6789 (invalid SSN 000-12-3456).";
        let res = scrub_text(raw, MaskingStrategy::Redact);
        assert!(res.cleaned_text.contains("[REDACTED_EMAIL]"));
        assert!(res.cleaned_text.contains("[REDACTED_SSN]"));
        assert!(res.cleaned_text.contains("000-12-3456"));
        assert_eq!(res.entities_found.get("EMAIL"), Some(&1));
        assert_eq!(res.entities_found.get("SSN"), Some(&1));
        assert_eq!(res.total_redacted, 2);
    }

    #[test]
    fn test_mask_and_hash_strategies() {
        let masked = scrub_text("SSN 123-45-6789", MaskingStrategy::Mask);
        assert_eq!(masked.cleaned_text, "SSN ***-**-6789");

        let hashed = scrub_text("alice@example.com", MaskingStrategy::Hash);
        assert!(hashed.cleaned_text.starts_with("[HASH_EMAIL_"));
    }
}
