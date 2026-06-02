# jobappscript
Job Application Automation Script

## Usage

```bash
python job_apply.py /path/to/resume_folder /path/to/job_description.pdf
```

Optional flags:
- `--output-folder /path/to/output`
- `--no-copilot` (uses local fallback resume generation)
- `--copilot-token-env GITHUB_TOKEN`
- `--copilot-endpoint https://models.inference.ai.azure.com/chat/completions`
- `--model gpt-4.1`

The script:
1. Validates required input paths (resume folder + job description PDF)
2. Reads resumes from the folder
3. Reads the job description PDF
4. Generates an ATS-format resume (Copilot call when token is available, with safe fallback)
5. Writes editable `generated_resume.md` to the output folder
6. Copies the job description PDF into the same output folder
