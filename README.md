---
title: I18n Agent
emoji: 🤖
colorFrom: blue
colorTo: green
sdk: gradio
sdk_version: "4.31.0"
app_file: app.py
pinned: false
---

# GitHub PR 에이전트

Langchain과 AWS Bedrock을 사용하여 GitHub PR을 자동으로 생성하는 AI 에이전트입니다.

## 기능

- 새로운 브랜치 생성
- 파일 생성 및 수정
- 여러 파일을 한 번에 커밋
- Pull Request 자동 생성
- AI 기반 PR 제목 및 본문 생성

## 필요 조건

- Python 3.8 이상
- GitHub Personal Access Token
- AWS 계정 (Bedrock 액세스 권한)
- 테스트용 GitHub 저장소

## 설치 방법

### 1. 저장소 클론 및 의존성 설치

```bash
# 의존성 설치
pip install -r requirements.txt

# 또는 setup.py 사용
pip install -e .
```

### 2. 환경 변수 설정

```bash
# env.example을 .env로 복사
cp env.example .env

# .env 파일을 편집하여 실제 값으로 변경
```

필수 환경 변수:
- `GITHUB_TOKEN`: GitHub Personal Access Token
- `AWS_ACCESS_KEY_ID`: AWS 액세스 키
- `AWS_SECRET_ACCESS_KEY`: AWS 시크릿 키
- `AWS_DEFAULT_REGION`: AWS 리전 (기본값: us-east-1)

## GitHub Token 생성 방법

1. GitHub → Settings → Developer settings → Personal access tokens → Tokens (classic)
2. "Generate new token" 클릭
3. 다음 권한 선택:
   - `repo` (전체 저장소 액세스)
   - `workflow` (GitHub Actions)
   - `write:packages` (패키지 쓰기)

## AWS Bedrock 설정

1. AWS 콘솔에서 Bedrock 서비스 활성화
2. Claude 모델에 대한 액세스 요청 및 승인
3. IAM 사용자에게 Bedrock 권한 부여

## 사용 방법

### 기본 테스트 실행

```bash
# 환경 변수 설정 후 실행
export GITHUB_TOKEN="your_token_here"
export GITHUB_TEST_OWNER="your_username"
export GITHUB_TEST_REPO="your_test_repo"

# 스크립트 실행
python github_pr_agent.py
```

### 에이전트 사용 예시

```python
from github_pr_agent import agent_executor

# 에이전트에게 작업 요청
user_input = {
    "input": """
    GitHub 작업을 수행하려 합니다. 제 GitHub 사용자 이름은 'your_username'이고, 
    작업할 저장소는 'your_repo'입니다.
    
    1. 'main' 브랜치를 기반으로 'feature-branch'를 생성해주세요.
    2. 'README.md' 파일을 추가하고 내용은 '# New Feature'로 해주세요.
    3. 'feature-branch'에서 'main'으로 PR을 생성해주세요.
    """
}

response = agent_executor.invoke(user_input)
print(response['output'])
```

## 테스트 방법

### 1. 테스트용 저장소 준비

1. GitHub에서 새 저장소 생성 (예: `test-pr-agent`)
2. README.md 파일로 초기 커밋 생성
3. 환경 변수에 저장소 정보 설정

### 2. 단위 테스트 실행

```bash
# 기본 함수 테스트
python -c "
import os
os.environ['GITHUB_TOKEN'] = 'your_token'
os.environ['GITHUB_TEST_OWNER'] = 'your_username'
os.environ['GITHUB_TEST_REPO'] = 'test-repo'
exec(open('github_pr_agent.py').read())
"
```

### 3. 주요 테스트 시나리오

1. **브랜치 생성 테스트**: 새로운 브랜치가 올바르게 생성되는지 확인
2. **파일 생성 테스트**: 새 파일이 브랜치에 커밋되는지 확인
3. **다중 파일 푸시 테스트**: 여러 파일을 한 번에 커밋하는지 확인
4. **PR 생성 테스트**: Pull Request가 올바르게 생성되는지 확인

## 문제 해결

### 일반적인 오류

1. **GITHUB_TOKEN 오류**
   - 토큰이 올바르게 설정되었는지 확인
   - 토큰 권한이 충분한지 확인

2. **AWS Bedrock 오류**
   - AWS 자격 증명이 올바른지 확인
   - Bedrock 서비스가 활성화되어 있는지 확인
   - Claude 모델 액세스가 승인되었는지 확인

3. **브랜치 생성 실패**
   - 저장소가 존재하는지 확인
   - 기본 브랜치에 최소 하나의 커밋이 있는지 확인

## 라이센스

MIT License 