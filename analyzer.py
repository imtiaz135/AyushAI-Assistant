import csv
import logging
import os
import pickle
import random
import re
from typing import Dict, List, Optional, Tuple

import pandas as pd
import pytesseract
from PIL import Image
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
try:
    from pypdf import PdfReader
except Exception:  # Optional dependency for PDF text extraction
    PdfReader = None
try:
    from pdf2image import convert_from_path
except Exception:  # Optional dependency for scanned PDF OCR fallback
    convert_from_path = None
try:
    import fitz  # PyMuPDF (poppler-free PDF rendering)
except Exception:  # Optional dependency for scanned PDF OCR fallback
    fitz = None

DATASET_PATH = "dataset.csv"
MODEL_PATH = "model.pkl"
DEFAULT_TESSERACT_WINDOWS_PATH = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
DEFAULT_POPPLER_WINDOWS_BIN = r"C:\Program Files\poppler\Library\bin"
MAX_OCR_PDF_PAGES = 10
logger = logging.getLogger(__name__)
_OCR_LANG_CACHE: Optional[str] = None


def _configure_tesseract() -> None:
    """Point pytesseract to the Tesseract binary when available."""
    configured_path = os.getenv("TESSERACT_CMD", "").strip()
    if configured_path and os.path.exists(configured_path):
        pytesseract.pytesseract.tesseract_cmd = configured_path
        return

    if os.name == "nt" and os.path.exists(DEFAULT_TESSERACT_WINDOWS_PATH):
        pytesseract.pytesseract.tesseract_cmd = DEFAULT_TESSERACT_WINDOWS_PATH


_configure_tesseract()


def _resolve_poppler_path() -> Optional[str]:
    configured = os.getenv("POPPLER_PATH", "").strip()
    if configured and os.path.exists(configured):
        return configured
    if os.name == "nt" and os.path.exists(DEFAULT_POPPLER_WINDOWS_BIN):
        return DEFAULT_POPPLER_WINDOWS_BIN
    return None


def _resolve_ocr_languages() -> str:
    """
    Use installed Tesseract languages dynamically.
    Prefers multilingual OCR when traineddata is available.
    """
    global _OCR_LANG_CACHE
    if _OCR_LANG_CACHE:
        return _OCR_LANG_CACHE

    preferred = ["eng", "hin", "ben", "mar", "tam", "tel", "urd", "osd"]
    try:
        installed = set(pytesseract.get_languages(config=""))
    except Exception:
        installed = set()

    selected = [lang for lang in preferred if lang in installed]
    if not selected:
        selected = ["eng"]
    if "osd" not in selected and "osd" in installed:
        selected.append("osd")

    _OCR_LANG_CACHE = "+".join(selected)
    logger.info("Using OCR languages: %s", _OCR_LANG_CACHE)
    return _OCR_LANG_CACHE


def _ocr_image(image: Image.Image) -> str:
    """Run OCR with installed language support and safe fallback."""
    lang = _resolve_ocr_languages()
    try:
        return pytesseract.image_to_string(image, lang=lang, config="--psm 6").strip()
    except Exception as lang_error:
        logger.warning("OCR with lang=%s failed, falling back: %s", lang, lang_error)
        return pytesseract.image_to_string(image, config="--psm 6").strip()


def _ocr_pdf_with_pymupdf(
    path: str,
    analyze_scope: str,
    selected_page: Optional[int],
    region: Optional[Tuple[int, int, int, int]],
) -> str:
    """
    Poppler-free PDF OCR fallback.

    Uses PyMuPDF to render pages to images, then runs Tesseract OCR on them.
    """
    if fitz is None:
        return ""

    try:
        doc = fitz.open(path)
    except Exception as e:
        logger.exception("PyMuPDF open failed: %s", e)
        return ""

    text_parts: List[str] = []
    try:
        if analyze_scope in {"current_page", "selected_area"}:
            target_page = selected_page or 1
            if 1 <= target_page <= doc.page_count:
                page_numbers = [target_page]
            else:
                page_numbers = []
        else:
            limit = min(doc.page_count, MAX_OCR_PDF_PAGES)
            page_numbers = list(range(1, limit + 1))

        for page_no in page_numbers:
            page = doc.load_page(page_no - 1)
            # Render at higher resolution for better OCR.
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
            image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

            if analyze_scope == "selected_area" and region is not None:
                x, y, width, height = region
                left = max(0, x)
                top = max(0, y)
                right = min(image.width, x + width)
                bottom = min(image.height, y + height)
                if right > left and bottom > top:
                    image = image.crop((left, top, right, bottom))

            ocr_text = _ocr_image(image)
            if ocr_text:
                text_parts.append(ocr_text)

                # If we're analyzing the full document, stop early once we see
                # enough dataset-like cues to proceed.
                if analyze_scope == "full_document":
                    partial = "\n".join(text_parts).strip()
                    # Quick keyword-based relevance check (no ML calls here).
                    relevant_hint = _extract_dataset_relevant_text(
                        partial, max_sentences=3, max_chars=1500
                    )
                    pl = partial.lower()
                    has_dataset_evidence = any(
                        term in pl
                        for term in [
                            "may",
                            "lifestyle",
                            "immune",
                            "digestive",
                            "joint",
                            "stress",
                            "skin",
                            "cognitive",
                            "respiratory",
                            "balanced diet",
                        ]
                    )
                    if relevant_hint and len(partial) >= 800 and has_dataset_evidence:
                        break
    finally:
        try:
            doc.close()
        except Exception:
            pass

    return "\n".join(text_parts).strip()


def _generate_text_samples(size: int = 900) -> List[List[str]]:
    """Create synthetic training rows with label 1 (authentic) and 0 (fake)."""
    authentic_subjects = [
        "Ashwagandha",
        "Turmeric",
        "Tulsi",
        "Triphala",
        "Giloy",
        "Amla",
        "Brahmi",
        "Neem",
        "Shatavari",
        "Licorice root",
    ]
    authentic_actions = [
        "may support",
        "is traditionally used to support",
        "can help maintain",
        "has been studied for",
        "is known in Ayurveda for supporting",
        "may assist with",
    ]
    authentic_benefits = [
        "stress response",
        "immune function",
        "digestive comfort",
        "joint health",
        "healthy inflammation balance",
        "respiratory wellness",
        "cognitive clarity",
        "skin health",
    ]
    authentic_qualifiers = [
        "when used with proper dosage",
        "as part of a balanced lifestyle",
        "under professional guidance",
        "alongside a healthy diet and sleep routine",
        "with regular follow-up",
    ]

    fake_openers = [
        "Miracle herb",
        "Secret ancient formula",
        "Guaranteed Ayurvedic hack",
        "Divine medicine",
        "Ultimate plant cure",
    ]
    fake_claims = [
        "cures all diseases instantly",
        "works 100% in one day",
        "reverses every illness forever",
        "replaces all doctors permanently",
        "gives guaranteed cure with zero effort",
        "heals any condition overnight",
    ]
    fake_addons = [
        "without diagnosis",
        "without medicine",
        "with no side effects ever",
        "for every person in the world",
        "with zero scientific proof needed",
    ]

    rows: List[List[str]] = []
    for _ in range(size // 2):
        authentic_text = (
            f"{random.choice(authentic_subjects)} {random.choice(authentic_actions)} "
            f"{random.choice(authentic_benefits)} {random.choice(authentic_qualifiers)}."
        )
        fake_text = (
            f"{random.choice(fake_openers)} {random.choice(fake_claims)} "
            f"{random.choice(fake_addons)}!"
        )
        rows.append([authentic_text, "1"])
        rows.append([fake_text, "0"])

    random.shuffle(rows)
    return rows


def ensure_dataset(min_rows: int = 900) -> None:
    """Create dataset.csv if missing or too small."""
    if os.path.exists(DATASET_PATH):
        try:
            existing = pd.read_csv(DATASET_PATH)
            if {"text", "label"}.issubset(existing.columns) and len(existing) >= min_rows:
                return
        except Exception:
            # Recreate corrupt or invalid file
            pass

    rows = _generate_text_samples(size=min_rows)
    with open(DATASET_PATH, "w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["text", "label"])
        writer.writerows(rows)


def train_and_save_model() -> None:
    """Train TF-IDF + Logistic Regression and save model.pkl."""
    ensure_dataset()
    if os.path.exists(MODEL_PATH):
        try:
            model_mtime = os.path.getmtime(MODEL_PATH)
            dataset_mtime = os.path.getmtime(DATASET_PATH)
            if model_mtime >= dataset_mtime:
                return
            logger.info("Retraining model because dataset changed.")
        except OSError:
            logger.info("Model timestamp check failed; retraining model.")

    data = pd.read_csv(DATASET_PATH)
    x_train = data["text"].astype(str)
    y_train = data["label"].astype(int)

    model = Pipeline(
        [
            ("tfidf", TfidfVectorizer(ngram_range=(1, 2), min_df=1)),
            ("classifier", LogisticRegression(max_iter=200)),
        ]
    )
    model.fit(x_train, y_train)

    with open(MODEL_PATH, "wb") as file:
        pickle.dump(model, file)


def _load_model() -> Pipeline:
    train_and_save_model()
    with open(MODEL_PATH, "rb") as file:
        return pickle.load(file)


def _parse_selected_region(selected_region: str) -> Tuple[Optional[int], Optional[Tuple[int, int, int, int]]]:
    """
    Parse region metadata sent by frontend.
    Format example: x:120, y:80, w:240, h:100, page:2
    """
    if not selected_region:
        return None, None

    page_match = re.search(r"page\s*:\s*(\d+)", selected_region, re.IGNORECASE)
    x_match = re.search(r"x\s*:\s*(-?\d+)", selected_region, re.IGNORECASE)
    y_match = re.search(r"y\s*:\s*(-?\d+)", selected_region, re.IGNORECASE)
    w_match = re.search(r"w\s*:\s*(\d+)", selected_region, re.IGNORECASE)
    h_match = re.search(r"h\s*:\s*(\d+)", selected_region, re.IGNORECASE)

    page_num = int(page_match.group(1)) if page_match else None
    if not all([x_match, y_match, w_match, h_match]):
        return page_num, None

    x = int(x_match.group(1))
    y = int(y_match.group(1))
    width = int(w_match.group(1))
    height = int(h_match.group(1))
    if width <= 0 or height <= 0:
        return page_num, None
    return page_num, (x, y, width, height)


def extract_text(path: str, analyze_scope: str = "full_document", selected_region: str = "") -> str:
    """Extract text from uploaded image/PDF using scope-aware OCR or PDF parsing."""
    selected_page, region = _parse_selected_region(selected_region)

    if path.lower().endswith(".pdf"):
        try:
            reader_text = ""
            if PdfReader is not None:
                reader = PdfReader(path)
                total_pages = len(reader.pages)

                if analyze_scope in {"current_page", "selected_area"}:
                    target_page = selected_page or 1
                    if 1 <= target_page <= total_pages:
                        reader_text = (reader.pages[target_page - 1].extract_text() or "").strip()
                else:
                    text_parts: List[str] = []
                    for page in reader.pages:
                        page_text = page.extract_text() or ""
                        if page_text.strip():
                            text_parts.append(page_text.strip())
                    reader_text = "\n".join(text_parts).strip()

            if reader_text:
                return reader_text.strip()

            # Fallback OCR for scanned PDFs (avoid requiring poppler).
            ocr_text_parts: List[str] = []

            if convert_from_path is not None:
                try:
                    poppler_path = _resolve_poppler_path()
                    kwargs = {"fmt": "png", "dpi": 200}
                    if poppler_path:
                        kwargs["poppler_path"] = poppler_path

                    if analyze_scope in {"current_page", "selected_area"}:
                        target_page = max(1, selected_page or 1)
                        images = convert_from_path(
                            path, first_page=target_page, last_page=target_page, **kwargs
                        )
                    else:
                        images = convert_from_path(
                            path, first_page=1, last_page=MAX_OCR_PDF_PAGES, **kwargs
                        )

                    for page_image in images:
                        ocr_text = _ocr_image(page_image)
                        if ocr_text:
                            ocr_text_parts.append(ocr_text)
                except Exception as ocr_err:
                    logger.warning("pdf2image OCR failed, trying PyMuPDF fallback: %s", ocr_err)

            if not ocr_text_parts:
                pymupdf_text = _ocr_pdf_with_pymupdf(path, analyze_scope, selected_page, region)
                if pymupdf_text:
                    ocr_text_parts.append(pymupdf_text)

            return "\n".join(ocr_text_parts).strip()
        except Exception:
            return ""

    try:
        image = Image.open(path)
        if analyze_scope == "selected_area" and region is not None:
            x, y, width, height = region
            left = max(0, x)
            top = max(0, y)
            right = min(image.width, x + width)
            bottom = min(image.height, y + height)
            if right > left and bottom > top:
                image = image.crop((left, top, right, bottom))
        text = _ocr_image(image)
        return text.strip()
    except Exception:
        return ""


def extract_text_with_debug(
    path: str, analyze_scope: str = "full_document", selected_region: str = ""
) -> Dict[str, object]:
    """Extract text with explicit status and debug logs for API use."""
    debug_logs: List[str] = []
    selected_page, region = _parse_selected_region(selected_region)

    try:
        debug_logs.append(f"Received file for OCR: {path}")
        logger.info("OCR start path=%s scope=%s selected=%s", path, analyze_scope, selected_region)

        if path.lower().endswith(".pdf"):
            debug_logs.append("Detected PDF input.")
            logger.info("PDF detected: %s", path)

            reader_text = ""
            if PdfReader is not None:
                try:
                    reader = PdfReader(path)
                    total_pages = len(reader.pages)
                    debug_logs.append(f"PDF parsed with {total_pages} pages.")
                    logger.info("PDF pages=%s", total_pages)
                    parts: List[str] = []

                    if analyze_scope in {"current_page", "selected_area"}:
                        target_page = selected_page or 1
                        if 1 <= target_page <= total_pages:
                            debug_logs.append(f"Processing page {target_page} via text parser.")
                            logger.info("Processing selected PDF page=%s", target_page)
                            reader_text = (reader.pages[target_page - 1].extract_text() or "").strip()
                    else:
                        limit = min(total_pages, MAX_OCR_PDF_PAGES)
                        for i in range(limit):
                            debug_logs.append(f"Processing page {i + 1} via text parser.")
                            logger.info("Processing PDF page=%s via parser", i + 1)
                            page_text = (reader.pages[i].extract_text() or "").strip()
                            if page_text:
                                parts.append(page_text)
                        reader_text = "\n".join(parts).strip()
                except Exception as parser_error:
                    logger.exception("PDF parser failed: %s", parser_error)
                    debug_logs.append(f"PDF text parser failed: {parser_error}")

            if reader_text:
                debug_logs.append("OCR completed using PDF text parser.")
                logger.info("OCR completed via PdfReader")
                return {"status": "success", "text": reader_text, "message": "", "logs": debug_logs}

            ocr_text_parts: List[str] = []

            # 1) Try pdf2image (requires poppler on PATH).
            if convert_from_path is not None:
                try:
                    poppler_path = _resolve_poppler_path()
                    debug_logs.append("Converting PDF to images for OCR fallback.")
                    logger.info("PDF OCR fallback started; poppler_path=%s", poppler_path or "default")

                    kwargs = {"fmt": "png", "dpi": 200}
                    if poppler_path:
                        kwargs["poppler_path"] = poppler_path

                    if analyze_scope in {"current_page", "selected_area"}:
                        target_page = max(1, selected_page or 1)
                        images = convert_from_path(
                            path, first_page=target_page, last_page=target_page, **kwargs
                        )
                    else:
                        images = convert_from_path(
                            path, first_page=1, last_page=MAX_OCR_PDF_PAGES, **kwargs
                        )

                    debug_logs.append(f"PDF converted to {len(images)} image page(s) via pdf2image.")
                    for index, page_image in enumerate(images, start=1):
                        debug_logs.append(f"Processing OCR on converted page {index}.")
                        logger.info("OCR on converted PDF page=%s", index)
                        ocr_text = _ocr_image(page_image)
                        if ocr_text:
                            ocr_text_parts.append(ocr_text)
                except Exception as ocr_err:
                    logger.warning("pdf2image OCR failed, will try PyMuPDF: %s", ocr_err)
                    debug_logs.append(f"pdf2image OCR failed: {ocr_err}")

            # 2) Poppler-free fallback via PyMuPDF.
            if not ocr_text_parts and fitz is not None:
                debug_logs.append("Trying poppler-free OCR fallback (PyMuPDF render).")
                pymupdf_text = _ocr_pdf_with_pymupdf(path, analyze_scope, selected_page, region)
                if pymupdf_text:
                    ocr_text_parts.append(pymupdf_text)

            if not ocr_text_parts:
                debug_logs.append("OCR fallback failed for PDF: no readable text found.")
                return {
                    "status": "error",
                    "text": "",
                    "message": "OCR completed but no readable text was found in the PDF.",
                    "logs": debug_logs,
                }

            final_pdf_text = "\n".join(ocr_text_parts).strip()
            debug_logs.append("OCR completed using PDF fallback.")
            return {"status": "success", "text": final_pdf_text, "message": "", "logs": debug_logs}

        debug_logs.append("Detected image input.")
        image = Image.open(path)
        if analyze_scope == "selected_area" and region is not None:
            x, y, width, height = region
            left = max(0, x)
            top = max(0, y)
            right = min(image.width, x + width)
            bottom = min(image.height, y + height)
            if right > left and bottom > top:
                debug_logs.append(f"Cropping selected area: x={left}, y={top}, w={right-left}, h={bottom-top}")
                image = image.crop((left, top, right, bottom))

        debug_logs.append("Running Tesseract OCR on image.")
        text = _ocr_image(image)
        if not text:
            return {
                "status": "error",
                "text": "",
                "message": "OCR completed but no readable text was found in the image.",
                "logs": debug_logs,
            }
        debug_logs.append("OCR completed successfully.")
        logger.info("OCR completed for image input")
        return {"status": "success", "text": text, "message": "", "logs": debug_logs}
    except Exception as error:
        logger.exception("OCR pipeline failed: %s", error)
        debug_logs.append(f"OCR pipeline error: {error}")
        return {"status": "error", "text": "", "message": str(error), "logs": debug_logs}


def _rule_based_analysis(text: str) -> Dict[str, object]:
    score = 70
    issues: List[str] = []
    lowered = text.lower()

    fake_patterns = [
        "100% cure",
        "cures all",
        "miracle",
        "instant cure",
        "guaranteed cure",
        "works overnight",
        "no doctor needed",
    ]
    authentic_patterns = [
        "may support",
        "traditionally used",
        "under guidance",
        "clinical",
        "research",
        "balanced diet",
        "lifestyle",
    ]

    for pattern in fake_patterns:
        if pattern in lowered:
            score -= 12
            issues.append(f"Exaggerated claim detected: '{pattern}'")

    for pattern in authentic_patterns:
        if pattern in lowered:
            score += 4

    words = re.findall(r"\b\w+\b", lowered)
    if len(words) < 12:
        score -= 10
        issues.append("Very short content; insufficient context.")
    if "." not in text and len(words) > 10:
        score -= 6
        issues.append("Sentence structure appears weak.")

    score = max(0, min(100, score))
    return {"score": score, "issues": issues}


def _extract_dataset_relevant_text(text: str, max_sentences: int = 8, max_chars: int = 4000) -> str:
    """
    Keep only OCR sentences that look like they belong to the dataset patterns.

    This reduces noise from OCR and makes the ML model score meaningful even on scanned PDFs.
    """
    cleaned = (text or "").strip()
    if not cleaned:
        return ""

    normalized = re.sub(r"\s+", " ", cleaned)
    sentences = re.split(r"(?<=[\.\!\?])\s+|\n+", normalized)

    # Keywords/phrases used in dataset generation + rule-based analysis.
    keywords = [
        # "Authentic-like" cues
        "may support",
        "may assist",
        "traditionally used",
        "under professional guidance",
        "under guidance",
        "clinical",
        "research",
        "balanced diet",
        "lifestyle",
        "immune function",
        "digestive comfort",
        "joint health",
        "healthy inflammation balance",
        "respiratory wellness",
        "cognitive clarity",
        "skin health",
        "stress response",
        "proper dosage",
        "regular follow-up",
        "sleep routine",
        "has been studied for",
        "is known in ayurveda",
        # Common dataset herb names (help when OCR varies the surrounding wording).
        "ashwagandha",
        "turmeric",
        "tulsi",
        "triphala",
        "giloy",
        "amla",
        "brahmi",
        "neem",
        "shatavari",
        "licorice root",
        # "Fake/exaggerated" cues
        "miracle",
        "secret ancient formula",
        "guaranteed ayurvedic hack",
        "divine medicine",
        "ultimate plant cure",
        "100% in one day",
        "100% cure",
        "guaranteed cure",
        "instant cure",
        "cures all",
        "works 100%",
        "zero scientific proof",
        "no side effects",
        "for every person in the world",
        "without diagnosis",
        "without medicine",
        "no doctor needed",
        "works overnight",
    ]
    keywords_lower = [k.lower() for k in keywords]

    kept: List[str] = []
    for s in sentences:
        ls = s.lower().strip()
        if not ls:
            continue
        if any(k in ls for k in keywords_lower):
            kept.append(s.strip())
            if len(kept) >= max_sentences:
                break

    if not kept:
        return ""

    combined = "\n".join(kept).strip()
    if len(combined) > max_chars:
        combined = combined[:max_chars].rsplit(" ", 1)[0].strip()
    return combined


def _extract_relevant_text_by_ml_confidence(
    text: str,
    model: Pipeline,
    max_sentences: int = 8,
    max_chars: int = 4000,
) -> str:
    """
    Fallback when keyword matching finds no relevant sentences.

    Splits OCR text into sentences and keeps the ones that strongly match the ML model.
    """
    cleaned = (text or "").strip()
    if not cleaned:
        return ""

    normalized = re.sub(r"\s+", " ", cleaned)
    sentences = re.split(r"(?<=[\.\!\?])\s+|\n+", normalized)
    candidates = [s.strip() for s in sentences if s and s.strip()]
    if not candidates:
        return ""

    # Cap to keep runtime predictable.
    candidates = candidates[:30]

    scored: List[Tuple[float, int, str]] = []
    for idx, s in enumerate(candidates):
        try:
            proba = model.predict_proba([s])[0]
            p_auth = float(proba[1])
            confidence = max(p_auth, 1.0 - p_auth)  # closeness to either class
            scored.append((confidence, idx, s))
        except Exception:
            continue

    if not scored:
        return ""

    scored.sort(key=lambda x: x[0], reverse=True)
    top = scored[:max_sentences]
    top_indices = {idx for _, idx, _ in top}

    kept_in_order = [candidates[i] for i in range(len(candidates)) if i in top_indices]
    combined = "\n".join(kept_in_order).strip()

    if len(combined) > max_chars:
        combined = combined[:max_chars].rsplit(" ", 1)[0].strip()
    return combined


def analyze_text(text: str) -> Dict[str, object]:
    """Combine rule score + ML confidence into final authenticity report."""
    cleaned_text = (text or "").strip()
    if not cleaned_text:
        return {
            "score": 0,
            "quality": "Needs Review",
            "issues": ["No text extracted from image. Check image quality and OCR setup."],
            "ml_label": "Fake / Exaggerated",
            "ml_confidence": 0.0,
        }

    model = _load_model()

    dataset_relevant_text = _extract_dataset_relevant_text(cleaned_text)
    if not dataset_relevant_text:
        dataset_relevant_text = _extract_relevant_text_by_ml_confidence(cleaned_text, model)

    analysis_text = dataset_relevant_text if dataset_relevant_text else cleaned_text

    proba = model.predict_proba([analysis_text])[0]
    ml_authentic_prob = float(proba[1])
    ml_score = int(ml_authentic_prob * 100)
    ml_label = "Authentic" if ml_authentic_prob >= 0.5 else "Fake / Exaggerated"

    rules = _rule_based_analysis(analysis_text)
    rule_score = int(rules["score"])
    issues = list(rules["issues"])

    final_score = int((0.55 * ml_score) + (0.45 * rule_score))
    final_score = max(0, min(100, final_score))

    if final_score >= 75:
        quality = "High Authenticity"
    elif final_score >= 50:
        quality = "Moderate Authenticity"
    else:
        quality = "Low Authenticity"

    if ml_label.startswith("Fake") and "ML model flagged exaggerated language." not in issues:
        issues.append("ML model flagged exaggerated language.")
    if not issues:
        issues.append("No major issues detected.")

    return {
        "score": final_score,
        "quality": quality,
        "issues": issues,
        "ml_label": ml_label,
        "ml_confidence": round(ml_authentic_prob * 100, 2),
        "dataset_relevant_text": dataset_relevant_text if dataset_relevant_text else cleaned_text[:1200].strip(),
    }