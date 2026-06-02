#!/usr/bin/env python3
"""Generate an ATS-focused resume from a folder of resumes and a job description PDF."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import urllib.error
import urllib.request
from pathlib import Path
from typing import Iterable
import os


SUPPORTED_RESUME_EXTENSIONS = {".txt", ".md", ".rtf", ".pdf", ".doc", ".docx"}


def extract_text_from_pdf(pdf_path: Path) -> str:
    """Best-effort PDF text extraction with optional pypdf support."""
    try:
        from pypdf import PdfReader  # type: ignore

        reader = PdfReader(str(pdf_path))
        pages = [page.extract_text() or "" for page in reader.pages]
        text = "\n".join(pages).strip()
        if text:
            return text
    except Exception:
        pass

    # Fallback for environments without PDF parser dependencies.
    raw = pdf_path.read_bytes().decode("latin-1", errors="ignore")
    matches = re.findall(r"\(([^()]{2,})\)", raw)
    if matches:
        return "\n".join(matches)
    return raw


def read_job_description(job_description_pdf: Path) -> str:
    if not job_description_pdf.exists():
        raise FileNotFoundError(f"Job description file not found: {job_description_pdf}")
    if job_description_pdf.suffix.lower() != ".pdf":
        raise ValueError("Job description must be a PDF file")
    return extract_text_from_pdf(job_description_pdf)


def read_resume_file(path: Path) -> str:
    if path.suffix.lower() == ".pdf":
        return extract_text_from_pdf(path)
    return path.read_text(encoding="utf-8", errors="ignore")


def read_resumes(resume_folder: Path) -> list[str]:
    if not resume_folder.exists() or not resume_folder.is_dir():
        raise FileNotFoundError(f"Resume folder not found: {resume_folder}")

    contents: list[str] = []
    for path in sorted(resume_folder.iterdir()):
        if path.is_file() and path.suffix.lower() in SUPPORTED_RESUME_EXTENSIONS:
            text = read_resume_file(path).strip()
            if text:
                contents.append(text)

    if not contents:
        raise ValueError(f"No readable resume files found in: {resume_folder}")

    return contents


def build_prompt(job_description: str, resumes: Iterable[str]) -> str:
    merged_resumes = "\n\n---\n\n".join(resumes)
    return (
        "You are GitHub Copilot. Create an ATS-friendly professional resume in markdown. "
        "Use the candidate background from the provided resumes and optimize for the job description. "
        "Return only the final resume in editable markdown format.\n\n"
        f"Job description:\n{job_description}\n\n"
        f"Source resumes:\n{merged_resumes}"
    )


def fallback_resume(job_description: str, resumes: Iterable[str]) -> str:
    combined = "\n".join(resumes)
    skills = sorted(
        {
            token
            for token in re.findall(r"[A-Za-z][A-Za-z0-9+.#-]{1,}", f"{job_description}\n{combined}")
            if token.lower()
            in {
                "python",
                "sql",
                "javascript",
                "typescript",
                "aws",
                "azure",
                "gcp",
                "docker",
                "kubernetes",
                "django",
                "flask",
                "react",
                "node",
                "git",
                "linux",
                "terraform",
                "ci/cd",
            }
        }
    )
    skills_line = ", ".join(skills) if skills else "Python, SQL, Git"

    summary_source = re.sub(r"\s+", " ", job_description).strip()
    summary = (summary_source[:300] + "...") if len(summary_source) > 300 else summary_source

    return (
        "# ATS-Optimized Resume\n\n"
        "## Professional Summary\n"
        f"Candidate tailored to this role: {summary}\n\n"
        "## Core Skills\n"
        f"- {skills_line}\n\n"
        "## Experience Highlights\n"
        "- Delivered impactful projects using technologies aligned with role requirements.\n"
        "- Collaborated across teams to ship reliable, production-ready features.\n"
        "- Improved process efficiency through automation and data-driven decisions.\n\n"
        "## Education\n"
        "- Add education details here\n\n"
        "## Certifications\n"
        "- Add relevant certifications here\n"
    )


def generate_with_copilot(prompt: str, model: str, endpoint: str, token: str) -> str:
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are GitHub Copilot, an expert ATS resume writer."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
    }

    req = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer " + token,
        },
    )

    with urllib.request.urlopen(req, timeout=90) as response:
        data = json.loads(response.read().decode("utf-8"))

    choices = data.get("choices") or []
    if not choices:
        raise ValueError("Copilot response did not include choices")

    message = choices[0].get("message") or {}
    content = message.get("content", "")
    if not content:
        raise ValueError("Copilot response did not include resume content")
    return content.strip()


def run_workflow(
    resume_folder: Path,
    job_description_pdf: Path,
    output_folder: Path | None = None,
    *,
    use_copilot: bool = True,
    model: str = "gpt-4.1",
    copilot_endpoint: str = "https://models.inference.ai.azure.com/chat/completions",
    copilot_token_env: str = "GITHUB_TOKEN",
) -> tuple[Path, Path]:
    resume_folder = resume_folder.resolve()
    job_description_pdf = job_description_pdf.resolve()
    output_folder = (output_folder or resume_folder).resolve()

    job_description = read_job_description(job_description_pdf)
    resumes = read_resumes(resume_folder)
    output_folder.mkdir(parents=True, exist_ok=True)
    prompt = build_prompt(job_description, resumes)

    generated_resume: str
    if use_copilot:
        token = os.getenv(copilot_token_env)
        if token:
            try:
                generated_resume = generate_with_copilot(prompt, model, copilot_endpoint, token)
            except (urllib.error.URLError, ValueError, TimeoutError):
                generated_resume = fallback_resume(job_description, resumes)
        else:
            generated_resume = fallback_resume(job_description, resumes)
    else:
        generated_resume = fallback_resume(job_description, resumes)

    resume_output = output_folder / "generated_resume.md"
    resume_output.write_text(generated_resume + "\n", encoding="utf-8")

    jd_output = output_folder / job_description_pdf.name
    if jd_output.resolve() != job_description_pdf.resolve():
        shutil.copy2(job_description_pdf, jd_output)

    return resume_output, jd_output


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate an ATS-optimized resume from a folder of resumes and a job description PDF."
    )
    parser.add_argument("resume_folder", help="Path to folder containing resume files")
    parser.add_argument("job_description_pdf", help="Path to job description PDF")
    parser.add_argument("--output-folder", help="Optional output folder (default: resume folder)")
    parser.add_argument("--model", default="gpt-4.1", help="Copilot model name")
    parser.add_argument(
        "--copilot-endpoint",
        default="https://models.inference.ai.azure.com/chat/completions",
        help="Copilot-compatible chat completion endpoint",
    )
    parser.add_argument(
        "--copilot-token-env",
        default="GITHUB_TOKEN",
        help="Environment variable containing Copilot token",
    )
    parser.add_argument(
        "--no-copilot",
        action="store_true",
        help="Disable Copilot API call and always use local fallback resume generation",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_folder = Path(args.output_folder).expanduser() if args.output_folder else None

    resume_output, jd_output = run_workflow(
        resume_folder=Path(args.resume_folder).expanduser(),
        job_description_pdf=Path(args.job_description_pdf).expanduser(),
        output_folder=output_folder,
        use_copilot=not args.no_copilot,
        model=args.model,
        copilot_endpoint=args.copilot_endpoint,
        copilot_token_env=args.copilot_token_env,
    )

    print(f"Generated resume: {resume_output}")
    print(f"Job description copy: {jd_output}")


if __name__ == "__main__":
    main()
