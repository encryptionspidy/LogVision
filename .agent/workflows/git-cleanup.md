---
description: how to perform conventional commits for git cleanup
---

Follow these steps to ensure the project history follows conventional commits:

1. **Review Changed Files**:
   ```bash
   git status
   ```

2. **Stage and Commit by Component**:
   - **Clustering**: `feat(clustering): implement TF-IDF and MiniBatchKMeans for log clustering`
   - **Anomaly Detection**: `feat(anomaly): add z-score statistical detector and weighted evaluator`
   - **Security**: `feat(security): implement JWT auth, RBAC, and dev-mode auto-auth`
   - **UI**: `feat(ui): premium refinement with upload modal, charts, and skeleton states`
   - **Fixes**: `fix(tests): resolve DEV_MODE isolation and oversized file upload handling`

3. **Rebase if Necessary**:
   If the history is messy, use interactive rebase to squash into clean commits:
   ```bash
   git rebase -i HEAD~N
   ```

4. **Verify**:
   ```bash
   git log --oneline
   ```
