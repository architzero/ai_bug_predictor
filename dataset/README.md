# Training Datasets

This directory contains the Git repositories used for training the bug prediction model.

## Required Repositories

Clone the following repositories into this directory:

```bash
# Python repositories
git clone https://github.com/psf/requests dataset/requests
git clone https://github.com/pallets/flask dataset/flask
git clone https://github.com/encode/httpx dataset/httpx
git clone https://github.com/tiangolo/fastapi dataset/fastapi
git clone https://github.com/celery/celery dataset/celery
git clone https://github.com/sqlalchemy/sqlalchemy dataset/sqlalchemy

# JavaScript/TypeScript repositories
git clone https://github.com/expressjs/express dataset/express
git clone https://github.com/axios/axios dataset/axios

# Java repository
git clone https://github.com/google/guava dataset/guava
```

## Directory Structure

After cloning, your structure should look like:

```
dataset/
├── requests/
├── flask/
├── httpx/
├── fastapi/
├── celery/
├── sqlalchemy/
├── express/
├── axios/
└── guava/
```

## Notes

- These repositories are used for cross-project validation
- Total: 9 repositories across 4 programming languages
- Combined: ~36,000 commits, 15 years of history
- The model is trained using leave-one-out cross-validation
