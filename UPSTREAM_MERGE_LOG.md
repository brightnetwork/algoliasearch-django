# Upstream Merge Log

Merging commits from `upstream/master` (https://github.com/algolia/algoliasearch-django) into fork.

## Summary

| Applied | Skipped |
|---------|---------|
| 8       | 33      |

## Commits Processed

| Commit | Description | Action | Reason |
|--------|-------------|--------|--------|
| `3a8be83` | feat: add links to FAQ | **Applied** | Clean merge |
| `7810c8f` | fix: prevent deprecation warning (set_extra_header) | Skipped | Fork uses v3 client, not v1.x |
| `c57e001` | test: prevent comparison error (_metadata in rules) | Skipped | Fork has rewritten tests with mocks |
| `9194e91` | test: fix dependency for Python 2.7/3.4 | Skipped | Fork dropped Python 2 |
| `c884ac8` | chore: bump version to 1.7.2 | Skipped | Fork is at 3.0.0 |
| `897f3f5` | chore: add setup.cfg directive | Skipped | Fork already has this |
| `21c5297` | Update documentation link | **Applied** | Clean merge |
| `55cce82` | chore(test): test against django 2.2/3.x | Skipped | Fork uses GitHub Actions + Django 3.2+ |
| `07d3177` | fix: remove MIDDLEWARE_CLASSES | Skipped | Fork already uses MIDDLEWARE |
| `1266fb7` | chore(deps): update algoliasearch to 2.x | Skipped | Fork uses v3 client |
| `b1cbf74` | Merge PR #299 | Skipped | Merge commit |
| `6e7d084` | Merge PR #303 | Skipped | Merge commit |
| `4ffda5a` | Merge PR #304 | Skipped | Merge commit |
| `a7198f8` | chore: bump version to 1.7.3 | Skipped | Fork is at 3.0.0 |
| `11be469` | docs: typo | **Applied** | Clean merge |
| `ab7577b` | chore: fix changelog | Skipped | Changelog diverged |
| `4443814` | chore(deps): update algoliasearch to 2.x (major) | Skipped | Fork did own v3 migration |
| `e78e6b5` | chore(setup): Containerize repository | **Applied** | Clean merge (Dockerfile) |
| `1d5b2be` | Apply suggestions from code review | **Applied** | Clean merge |
| `6684b61` | wip: add docker build to travis | Skipped | Fork uses GitHub Actions |
| `17832af` | tests(docker): enable docker on travis | Skipped | Fork uses GitHub Actions |
| `97bb10a` | fix(UserAgent): migrate for 2.x client | Skipped | Fork uses v3 client |
| `68c8e7e` | fix: remove unnecessary reformatting | Skipped | Empty (already applied) |
| `6911521` | docs(compat): clarify Django 2.x/3.x compat | Skipped | Outdated for fork |
| `662435e` | docs: add env parameter | **Applied** | Clean merge |
| `25eef7c` | Merge PR #311 | Skipped | Merge commit |
| `d8320cd` | Merge PR #310 | Skipped | Merge commit |
| `4b7913c` | Update version.py | Skipped | Version conflict |
| `5b53a15` | docs(contributing): add tests command | **Applied** | Clean merge |
| `b5df401` | Merge PR #313 | Skipped | Merge commit |
| `e192aec` | Merge PR #306 | Skipped | Merge commit |
| `0dabc7c` | chore: bump version to 2.0.0 | Skipped | Fork is at 3.0.0 |

| `5bcc995` | build: Add django 3.2 tests with python 3.6/3.8 | Skipped | Fork already supports Django 3.2+ |
| `4a25fc2` | Merge PR #316 | Skipped | Merge commit |
| `3dacdbf` | feat: add support for Python 3.9, 3.10 and 3.11 | Skipped | Fork already has this support |
| `359da87` | feat!: drop python 2.7, update tox and CI | Skipped | Fork already dropped Python 2 |
| `2233054` | chore: bump to 3.0.0 | Skipped | Fork already at 3.0.0 |
| `7f23fc2` | chore: add release process | Skipped | Fork has own release process |
| `b71984f` | feat!: support new algoliasearch and django versions | **Applied** | Major v4 upgrade - cherry-picked with manual conflict resolution |
| `e869b15` | fix: remove highlightResult from response | **Applied** | Manually applied to models/base.py (fork uses package structure) |
| `cbf5df0` | chore: release v4 | Skipped | CI/release config - fork has own process |

## Notes

### v4 Migration (b71984f)
The fork was upgraded from algoliasearch v3 to v4 API. Key changes:
- Import `SearchClientSync` instead of `SearchClient.create_with_config`
- Direct client method calls with index_name as first parameter
- `save_object()` → `save_objects()`
- `search()` → `search_single_index().to_dict()`
- `move_index()` → `operation_index()` with `OperationIndexParams`
- Response handling with `.task_id` and `wait_for_task()`

Fork-specific features preserved:
- Aggregator pattern (multiple models in one index)
- `--index` flag in management commands
- GitHub Actions CI workflow
