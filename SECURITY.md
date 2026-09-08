# Security

Please do not disclose a suspected vulnerability, credential exposure, private source leak, or unsafe external-processing path in a public issue.

## Private reporting route

Use GitHub's **Security** tab and choose **Report a vulnerability**. The maintainer enables private vulnerability reporting before publishing a release. Include the affected version or commit, a minimal reproduction, impact, and whether any private data or credentials may have been exposed. Do not attach secrets or customer material; redact them and describe the location privately.

The maintainer should acknowledge receipt privately, confirm whether the report is in scope, and coordinate a fix or disclosure date before public disclosure.

## Scope

In scope are unsafe path handling, unintended writes into an installed Skill, credential or private-data leakage, permission bypass, malicious fixture provenance, and documentation that instructs unauthorized external processing or publication.

Out of scope are ordinary model mistakes, imperfect generated typography, aesthetic disagreement, consumer preference, and production or regulatory validation that this concept-stage Skill explicitly does not provide.

Do not run untrusted Skill code against private inputs. Review permissions and output roots before using external image tools, and keep private acceptance tests outside this public repository.
