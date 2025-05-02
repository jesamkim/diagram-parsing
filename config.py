# AWS Bedrock 설정
BEDROCK_REGION = 'us-west-2'
#BEDROCK_NOVA_PRO_MODEL_ID = 'us.amazon.nova-pro-v1:0'  # 기존 Nova Pro 모델
BEDROCK_NOVA_PRO_MODEL_ID = 'us.amazon.nova-premier-v1:0'  # 새로운 Nova Premier 모델
BEDROCK_NOVA_LITE_MODEL_ID = 'us.amazon.nova-lite-v1:0'
BEDROCK_CLAUDE_MODEL_ID = 'us.anthropic.claude-3-7-sonnet-20250219-v1:0'

# 파일 경로 설정
TEMP_DIR = './temp'
OUTPUT_DIR = './output'

# API 설정
MAX_RETRIES = 5  # 재시도 최대 횟수 증가 (3 -> 5)
BASE_WAIT_TIME = 10  # 기본 대기 시간 증가 (3초 -> 10초)

# 청크 크기 설정 (마크다운 생성용)
CHUNK_SIZE = 4000

# 이미지 설정
IMAGE_QUALITY = 300  # DPI for high-res images
LOW_RES_IMAGE_QUALITY = 72  # 초기 스캔용 저해상도 DPI
IMAGE_FORMAT = 'PNG'

# 도면 분석 설정
MAX_TOKENS_DRAWING_ANALYSIS = 5000
