import re

class ResumeSanitizer:
    def __init__(self, text):
        self.text = text
        self.issues = []
        self.score = 100

    def run_audit(self):
        """Runs all WSO compliance checks."""
        self._check_gpa()
        self._check_objective()
        self._check_forbidden_words()
        self._check_section_order()
        return self.issues, self.score

    def _check_gpa(self):
        # Rule: IF GPA < 3.0, REMOVE it (unless major GPA > 3.2)
        gpa_pattern = r"GPA\s*[:\-]?\s*(\d\.\d+)"
        matches = re.findall(gpa_pattern, self.text, re.IGNORECASE)
        
        for gpa in matches:
            try:
                score = float(gpa)
                if score < 3.0:
                    # Check for Major GPA context nearby (simplified logic)
                    if "major" not in self.text.lower() or "3.2" not in self.text:
                        self.issues.append(f"CRITICAL: Found GPA {score} (< 3.0). MUST REMOVE unless Major GPA > 3.2.")
                        self.score -= 20
            except ValueError:
                pass

    def _check_objective(self):
        # Rule: NO objective statements
        if "OBJECTIVE" in self.text.upper():
            self.issues.append("CRITICAL: 'OBJECTIVE' section found. Delete immediately. Reallocate space to deal experience.")
            self.score -= 15

    def _check_forbidden_words(self):
        # Rule: Bullets must be Result/Impact. Avoid passive voice.
        # "Responsible for" is the enemy of a WSO resume.
        forbidden = ["responsible for", "assisted with", "helped", "worked on"]
        for word in forbidden:
            if word in self.text.lower():
                self.issues.append(f"WEAK LANGUAGE: Found '{word}'. Replace with active verbs (e.g., 'Spearheaded', 'Executed').")
                self.score -= 5

    def _check_section_order(self):
        # Rule: Education goes BELOW Experience for experienced hires
        # Heuristic: If "Professional Experience" appears after "Education", flag it for review.
        edu_idx = self.text.upper().find("EDUCATION")
        exp_idx = self.text.upper().find("EXPERIENCE")
        
        if edu_idx > -1 and exp_idx > -1:
            if edu_idx < exp_idx:
                self.issues.append("FORMATTING: 'Education' is above 'Experience'. Verify if candidate is Experienced Hire (>1 year FT). If so, swap.")

    def generate_email_draft(self, student_name):
        # Rule: Turnaround 48 hrs for 1st draft
        issue_bullets = "\n".join([f"- {issue}" for issue in self.issues])
        
        return f"""
SUBJECT: Resume Feedback - {student_name} - Action Required

Hi {student_name},

I've reviewed your resume against the WSO strict formatting guidelines. 
Please address the following CRITICAL items within 48 hours:

{issue_bullets}

GENERAL GUIDANCE:
- Ensure all bullets follow the "Result + How" structure.
- Remove any passive language ("Responsible for").
- If your GPA is below 3.0, it must be removed entirely.

Please revise and reply with V2.

Best,
Head Mentor
"""