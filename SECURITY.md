# Security

This repository is a sample: it shows a pattern and is provided as is, under the [MIT licence](LICENSE).

## Reporting a vulnerability

Please do not report security issues in a public issue. Report them privately on GitHub instead: on this repository's **Security** tab, choose **Report a vulnerability**. Describe what you found, how to reproduce it and what it affects.

## Using the sample safely

- Deploy it in a subscription and a tenant meant for tests and demonstrations: its sizes and settings are chosen for that, not for production.
- Nothing secret is committed. The keys and the one client secret it needs are created at deployment and kept in Key Vault (README, "Design notes").
- Only the members of the chat users' group can sign in to the chat (README, "Open and share the chat").
- Delete the environment when you no longer need it (README, "Clean up").
