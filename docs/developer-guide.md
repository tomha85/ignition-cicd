# Developer guide

Use a feature branch, backup before modifying native project files, maintain byte-identical legacy mirrors where required, and verify `python -m unittest discover -s tests -v` plus `python framework/cli/check_repo.py`. The reusable staging workflow targets an explicitly allowlisted TEST Controller. See [detailed guide](DEVELOPER_GUIDE_V2.md).
