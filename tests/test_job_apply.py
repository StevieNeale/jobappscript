import tempfile
import unittest
from pathlib import Path

from job_apply import run_workflow


class JobApplyWorkflowTests(unittest.TestCase):
    def test_run_workflow_writes_resume_and_job_description_copy(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            resume_folder = base / "resumes"
            resume_folder.mkdir()

            (resume_folder / "resume1.txt").write_text(
                "Software Engineer with Python and SQL experience.", encoding="utf-8"
            )
            (resume_folder / "resume2.md").write_text(
                "Built cloud apps with Docker and AWS.", encoding="utf-8"
            )

            job_pdf = base / "job_description.pdf"
            job_pdf.write_bytes(
                b"%PDF-1.4\n(We need a Python engineer with AWS and SQL skills.)\n%%EOF"
            )

            output_folder = base / "output"
            resume_output, jd_output = run_workflow(
                resume_folder=resume_folder,
                job_description_pdf=job_pdf,
                output_folder=output_folder,
                use_copilot=False,
            )

            self.assertTrue(resume_output.exists())
            self.assertTrue(jd_output.exists())

            content = resume_output.read_text(encoding="utf-8")
            self.assertIn("ATS-Optimized Resume", content)
            self.assertIn("Python", content)

    def test_missing_resume_folder_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            job_pdf = base / "job_description.pdf"
            job_pdf.write_bytes(b"%PDF-1.4\n(Job details)\n%%EOF")

            with self.assertRaises(FileNotFoundError):
                run_workflow(
                    resume_folder=base / "missing",
                    job_description_pdf=job_pdf,
                    use_copilot=False,
                )

    def test_no_resume_files_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            resume_folder = base / "resumes"
            resume_folder.mkdir()
            job_pdf = base / "job_description.pdf"
            job_pdf.write_bytes(b"%PDF-1.4\n(Job details)\n%%EOF")

            with self.assertRaises(ValueError):
                run_workflow(
                    resume_folder=resume_folder,
                    job_description_pdf=job_pdf,
                    use_copilot=False,
                )


if __name__ == "__main__":
    unittest.main()
