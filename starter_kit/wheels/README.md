Place prebuilt Python wheels here when your held-out submission needs packages
that are not already installed in the official LakeQuest Docker image.

The held-out runner installs `requirements.txt` offline into a temporary
dependency directory with:

```bash
python -m pip install --target /tmp/lakequest_submission_deps \
  --no-index --find-links wheels -r requirements.txt
```

If `requirements.txt` is empty or only comments, no wheel files are needed.
