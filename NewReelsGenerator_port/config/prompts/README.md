Account-specific GPT prompts
===========================

Place one YAML file per account under this folder. The filename must match the
account key you pass in the generate payload (e.g., account: "alex" -> alex.yaml).

Each file must contain two keys:

- description:         Full prompt template for mode "titles" (generate descriptions only).
- title_description:   Full prompt template for mode "topics" (generate pairs Title|||Description with lines separated by ---).

Example (alex.yaml):

  description: |
    ... your full prompt for descriptions ...

  title_description: |
    ... your full prompt for (Title|||Description) pairs ...

Notes:
- Files must be UTF-8 encoded.
- If a prompt file or required key is missing, generation will fail with an explicit error.

Optional:
- extends: <account> — inherit prompts from another account file. The child overrides any keys it defines.
  Example:
    extends: alex
    footer: "Follow @example for more"
