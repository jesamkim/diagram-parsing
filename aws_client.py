import json
import boto3
import base64
from PIL import Image
import io
import traceback
import pathlib
from config import (
    BEDROCK_REGION, 
    BEDROCK_NOVA_PRO_MODEL_ID,
    BEDROCK_NOVA_LITE_MODEL_ID,
    BEDROCK_CLAUDE_MODEL_ID, 
    MAX_RETRIES, 
    MAX_TOKENS_DRAWING_ANALYSIS
)
from utils import wait_with_backoff

# Langchain 관련 import
from langchain_aws import ChatBedrock, ChatBedrockConverse
from langchain_core.messages import HumanMessage

class BedrockClient:
    def __init__(self):
        """Amazon Bedrock 클라이언트 초기화"""
        self.client = boto3.client(
            service_name='bedrock-runtime',
            region_name=BEDROCK_REGION
        )
    
    def encode_image_to_base64(self, image_path):
        """이미지 파일을 base64로 인코딩"""
        try:
            with Image.open(image_path) as img:
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                buffer = io.BytesIO()
                img.save(buffer, format='JPEG')
                return base64.b64encode(buffer.getvalue()).decode('utf-8')
        except Exception as e:
            print(f"이미지 인코딩 오류: {str(e)}")
            traceback.print_exc()
            return None

    def analyze_drawing_with_nova_langchain(self, image_path, context=None, retry_count=0):
        """Langchain을 사용하여 Nova Pro 모델로 도면 분석
        
        Args:
            image_path: 도면 이미지 경로
            context: 도면 관련 컨텍스트 정보 (선택적)
            retry_count: 재시도 횟수
            
        Returns:
            dict: 도면 분석 결과
        """
        try:
            # 이미지 파일을 읽어서 JPEG로 명시적 변환
            with Image.open(image_path) as img:
                img = img.convert('RGB')  # PNG의 알파 채널 제거
                jpeg_buffer = io.BytesIO()
                img.save(jpeg_buffer, format='JPEG')
                base64_image = base64.b64encode(jpeg_buffer.getvalue()).decode('utf-8')
            
            # 프롬프트 구성
            prompt = """
도면을 상세히 분석하고 다음 정보를 제공해주세요:

1. 도면 유형: 어떤 종류의 도면인지 파악 (건축, 기계, 전기, 배관 등)
2. 주요 구성 요소: 도면에 표시된 주요 구성 요소들을 식별
3. 수치 및 치수: 도면에 표시된 모든 수치와 치수를 정확히 기록
4. 주석 및 특수 기호: 도면에 표시된 주석과 특수 기호의 의미 해석
5. 좌표 및 방위: 도면에 좌표계나 방위가 표시된 경우 이를 명시
6. 테이블 형식 정보: 표로 작성되어 있는 데이터는 마크다운 테이블 형식으로 구조화

반환 형식:
- 분석 결과는 마크다운 형식으로 구조화해주세요.
- 테이블 데이터는 마크다운 표 형식으로 정확히 작성해주세요.
- 수치와 단위는 정확하게 기록해주세요.
"""
            
            # 컨텍스트 정보가 있으면 프롬프트에 추가
            if context:
                prompt += f"\n\n관련 컨텍스트 정보:\n{context}"
            
            # Nova Pro 모델 초기화
            chat = ChatBedrock(
                model_id=BEDROCK_NOVA_PRO_MODEL_ID,
                region_name=BEDROCK_REGION,
                model_kwargs={
                    "temperature": 0.2,
                    "maxTokens": MAX_TOKENS_DRAWING_ANALYSIS
                }
            )
            
            # 멀티모달 메시지 구성
            message = HumanMessage(
                content=[
                    {
                        "type": "text", 
                        "text": prompt
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{base64_image}"
                        }
                    }
                ]
            )
            
            # 모델 호출 (최대 재시도 횟수만큼)
            for i in range(MAX_RETRIES + 1):
                try:
                    response = chat.invoke([message])
                    break
                except Exception as e:
                    if i < MAX_RETRIES:
                        wait_time = 2**i * 3
                        print(f"오류 발생, {wait_time}초 후 재시도... (시도 {i+1}/{MAX_RETRIES})")
                        wait_with_backoff(i)
                    else:
                        raise e
            
            # 결과 확인 및 반환
            analysis_text = response.content
            print(f"도면 분석 완료: {len(analysis_text)} 글자")
            return {
                "analysis": analysis_text,
                "success": True
            }
            
        except Exception as e:
            print(f"도면 분석 오류 (Langchain): {str(e)}")
            traceback.print_exc()
            
            # 오류 발생 시 기존 방식으로 시도 (대체 방안)
            print("기존 직접 API 호출 방식으로 시도합니다...")
            return self.analyze_drawing_with_nova(image_path, context, retry_count)

    def analyze_drawing_with_nova(self, image_path, context=None, retry_count=0):
        """직접 API 호출을 사용하여 Nova Pro 모델로 도면 분석 (하위 호환성 유지)
        
        Args:
            image_path: 도면 이미지 경로
            context: 도면 관련 컨텍스트 정보 (선택적)
            retry_count: 재시도 횟수
            
        Returns:
            dict: 도면 분석 결과
        """
        try:
            # 이미지 파일을 읽어서 JPEG로 명시적 변환
            with Image.open(image_path) as img:
                img = img.convert('RGB')  # PNG의 알파 채널 제거
                jpeg_buffer = io.BytesIO()
                img.save(jpeg_buffer, format='JPEG')
                base64_image = base64.b64encode(jpeg_buffer.getvalue()).decode('utf-8')
            
            # 프롬프트 구성
            prompt = """
도면을 상세히 분석하고 다음 정보를 제공해주세요:

1. 도면 유형: 어떤 종류의 도면인지 파악 (건축, 기계, 전기, 배관 등)
2. 주요 구성 요소: 도면에 표시된 주요 구성 요소들을 식별
3. 수치 및 치수: 도면에 표시된 모든 수치와 치수를 정확히 기록
4. 주석 및 특수 기호: 도면에 표시된 주석과 특수 기호의 의미 해석
5. 좌표 및 방위: 도면에 좌표계나 방위가 표시된 경우 이를 명시
6. 테이블 형식 정보: 표로 작성되어 있는 데이터는 마크다운 테이블 형식으로 구조화

반환 형식:
- 분석 결과는 마크다운 형식으로 구조화해주세요.
- 테이블 데이터는 마크다운 표 형식으로 정확히 작성해주세요.
- 수치와 단위는 정확하게 기록해주세요.
"""
            
            # 컨텍스트 정보가 있으면 프롬프트에 추가
            if context:
                prompt += f"\n\n관련 컨텍스트 정보:\n{context}"
            
            # API 요청 구성 (Nova Lite와 유사한 간단한 형식으로 시도)
            body = {
                "prompt": prompt,
                "imageBase64String": base64_image,
                "textGenerationConfig": {
                    "maxTokenCount": MAX_TOKENS_DRAWING_ANALYSIS,
                    "temperature": 0.0
                }
            }
            
            # API 호출
            response = self.client.invoke_model(
                modelId=BEDROCK_NOVA_PRO_MODEL_ID,
                body=json.dumps(body)
            )
            
            # 응답 처리
            response_body = json.loads(response.get('body').read())
            print(f"Nova Pro 응답 구조: {response_body}")
            
            # 응답 구조에 따라 텍스트 추출 로직 조정
            if 'results' in response_body and len(response_body['results']) > 0:
                analysis_text = response_body['results'][0].get('outputText', '')
            elif 'outputText' in response_body:
                analysis_text = response_body['outputText']
            elif 'content' in response_body and len(response_body['content']) > 0:
                analysis_text = response_body['content'][0]['text']
            else:
                analysis_text = '도면 분석 결과를 추출할 수 없습니다.'
                print("응답에서 텍스트를 찾을 수 없습니다. 전체 응답:", response_body)
            
            return {
                "analysis": analysis_text,
                "success": True
            }
            
        except Exception as e:
            if "ThrottlingException" in str(e) and retry_count < MAX_RETRIES:
                print(f"API 호출 제한 오류. {2**retry_count * 3}초 후 재시도... (시도 {retry_count + 1}/{MAX_RETRIES})")
                wait_with_backoff(retry_count)
                return self.analyze_drawing_with_nova(image_path, context, retry_count + 1)
            else:
                print(f"도면 분석 오류: {str(e)}")
                traceback.print_exc()
                return {
                    "error": str(e),
                    "success": False
                }

    def is_drawing_with_nova_lite_langchain(self, image_path, retry_count=0):
        """Langchain을 사용하여 Nova Lite 모델로 이미지가 도면인지 판별
        
        Args:
            image_path: 이미지 파일 경로
            retry_count: 재시도 횟수
            
        Returns:
            bool: 이미지가 도면인지 여부
        """
        try:
            # 이미지 파일을 읽어서 JPEG로 명시적 변환
            with Image.open(image_path) as img:
                img = img.convert('RGB')  # PNG의 알파 채널 제거
                jpeg_buffer = io.BytesIO()
                img.save(jpeg_buffer, format='JPEG')
                base64_image = base64.b64encode(jpeg_buffer.getvalue()).decode('utf-8')
            
            # 파일 이름에서 불필요한 접미사 제거하여 간결하게 표시
            page_name = pathlib.Path(image_path).stem
            page_name = page_name.replace("_preview", "")  # _preview 접미사 제거
            print(f"페이지 {page_name} 분석 중...")
            
            # Nova Lite 모델 초기화 (ChatBedrock으로 변경)
            chat = ChatBedrock(
                model_id=BEDROCK_NOVA_LITE_MODEL_ID,
                region_name=BEDROCK_REGION,
                model_kwargs={
                    "temperature": 0.0,
                    "maxTokens": 10
                }
            )
            
            # 멀티모달 메시지 구성
            message = HumanMessage(
                content=[
                    {
                        "type": "text", 
                        "text": """이 이미지가 기술 도면, 건축 도면, 설계 도면인지 판단해주세요.
이미지에 직선, 도형, 치수, 기술적 표기가 많고 텍스트가 적으면 도면일 가능성이 높습니다.
도면이면 "YES"만 답변하고, 도면이 아니면 "NO"만 답변해주세요."""
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{base64_image}"
                        }
                    }
                ]
            )
            
            # 모델 호출 (최대 재시도 횟수만큼)
            for i in range(MAX_RETRIES + 1):
                try:
                    response = chat.invoke([message])
                    break
                except Exception as e:
                    if i < MAX_RETRIES:
                        wait_time = 2**i * 3
                        print(f"오류 발생, {wait_time}초 후 재시도... (시도 {i+1}/{MAX_RETRIES})")
                        wait_with_backoff(i)
                    else:
                        raise e
            
            # 결과 확인 및 반환
            output_text = response.content.upper()
            # 응답에서 YES/NO만 추출하여 표시
            decision = "YES" if "YES" in output_text else "NO"
            print(f"도면 여부 확인: {decision}")
            return "YES" in output_text
            
        except Exception as e:
            print(f"도면 식별 오류 (Langchain): {str(e)}")
            traceback.print_exc()
            
            # 오류 발생 시 기존 방식으로 시도 (대체 방안)
            print("기존 직접 API 호출 방식으로 시도합니다...")
            return self.is_drawing_with_nova_lite(image_path, retry_count)
    
    def is_drawing_with_nova_lite(self, image_path, retry_count=0):
        """기존 방식으로 Nova Lite 모델을 사용하여 이미지가 도면인지 판별
        
        Args:
            image_path: 이미지 파일 경로
            retry_count: 재시도 횟수
            
        Returns:
            bool: 이미지가 도면인지 여부
        """
        try:
            base64_image = self.encode_image_to_base64(image_path)
            if not base64_image:
                return False
            
            # 프롬프트 구성
            prompt = """이 이미지가 기술 도면, 건축 도면, 설계 도면인지 판단해주세요.
이미지에 직선, 도형, 치수, 기술적 표기가 많고 텍스트가 적으면 도면일 가능성이 높습니다.
도면이면 "YES"만 답변하고, 도면이 아니면 "NO"만 답변해주세요."""
            
            # API 요청 구성 (Nova Pro와 동일한 형식으로 통일)
            body = {
                "schemaVersion": "messages-v1",
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": prompt
                            },
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/jpeg",
                                    "data": base64_image
                                }
                            }
                        ]
                    }
                ],
                "inferenceConfig": {
                    "maxTokens": 10,
                    "temperature": 0.0
                }
            }
            
            # API 호출
            response = self.client.invoke_model(
                modelId=BEDROCK_NOVA_LITE_MODEL_ID,
                body=json.dumps(body)
            )
            
            # 응답 처리
            response_body = json.loads(response.get('body').read())
            print(f"Nova Lite 응답 구조: {response_body}")
            
            # 응답 구조에 따라 텍스트 추출 로직 조정
            if 'results' in response_body and len(response_body['results']) > 0:
                output_text = response_body['results'][0].get('outputText', '').upper()
            elif 'outputText' in response_body:
                output_text = response_body['outputText'].upper()
            elif 'content' in response_body and len(response_body['content']) > 0:
                output_text = response_body['content'][0]['text'].upper()
            else:
                output_text = ''
                print("응답에서 텍스트를 찾을 수 없습니다. 전체 응답:", response_body)
            
            # "YES"가 포함된 경우 도면으로 판단
            decision = "YES" if "YES" in output_text else "NO"
            print(f"도면 여부 확인: {decision}")
            return "YES" in output_text
            
        except Exception as e:
            if "ThrottlingException" in str(e) and retry_count < MAX_RETRIES:
                print(f"API 호출 제한 오류. {2**retry_count * 3}초 후 재시도... (시도 {retry_count + 1}/{MAX_RETRIES})")
                wait_with_backoff(retry_count)
                return self.is_drawing_with_nova_lite(image_path, retry_count + 1)
            else:
                print(f"도면 식별 오류: {str(e)}")
                traceback.print_exc()
                return False
    
    def process_chunk_with_claude(self, chunk, pdf_name, retry_count=0):
        """Claude 3.7 Sonnet 모델을 사용하여 마크다운 청크 처리
        
        Args:
            chunk: 처리할 마크다운 청크
            pdf_name: PDF 파일명
            retry_count: 재시도 횟수
            
        Returns:
            str: 처리된 마크다운 청크 내용
        """
        try:
            # 프롬프트 구성
            prompt = f"""
당신은 PDF 문서의 원본 내용을 유지하면서 도면 이미지 및 분석 결과를 통합하는 전문가입니다.
"{pdf_name}" 문서의 마크다운 형식을 그대로 유지하면서 도면 이미지와 분석 결과를 적절히 표시해주세요.
이 내용은 전체 문서의 일부분입니다.

중요: 이 작업은 원본 PDF 내용을 보존하는 것이 핵심입니다. 템플릿이나 예시 내용으로 대체하지 마세요!

절대적으로 지켜야 할 규칙:
1. 제공된 원본 마크다운 내용을 최대한 그대로 보존하세요. PDF에서 추출된 원본 텍스트를 삭제하거나 요약하지 마세요.
2. 도면 이미지와 분석 결과가 이미 마크다운에 삽입되어 있으니, 이 형식을 그대로 유지하세요.
3. 이미지 참조 형식(![도면 이미지](경로))을 정확히 유지하세요.
4. 도면 분석에 있는 표 형식을 유지하세요.
5. 페이지 구분자(<!-- page X -->)를 보존하세요.
6. 문서 전체적으로 일관된 헤더 수준을 유지하세요.
7. 실제 내용이 없는 빈 섹션이나 "내용이 제공되지 않았습니다"와 같은 텍스트를 제거하세요.
8. 청크의 시작과 끝이 문장 중간에 끊길 수 있으므로 불완전한 문장은 그대로 유지하세요.

원본 마크다운 내용:
```
{chunk}
```

작업할 마크다운을 제공해주세요. "다음과 같이 정리했습니다"와 같은 안내 문구 없이 바로 마크다운 내용을 시작하세요.
"""
            
            # API 요청 구성
            body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 4000,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": prompt
                            }
                        ]
                    }
                ]
            }
            
            # API 호출
            response = self.client.invoke_model(
                modelId=BEDROCK_CLAUDE_MODEL_ID,
                body=json.dumps(body)
            )
            
            # 응답 처리
            response_body = json.loads(response.get('body').read())
            return response_body['content'][0]['text']
            
        except Exception as e:
            if "ThrottlingException" in str(e) and retry_count < MAX_RETRIES:
                print(f"API 호출 제한 오류. {2**retry_count * 3}초 후 재시도... (시도 {retry_count + 1}/{MAX_RETRIES})")
                wait_with_backoff(retry_count)
                return self.process_chunk_with_claude(chunk, pdf_name, retry_count + 1)
            else:
                print(f"마크다운 청크 처리 오류: {str(e)}")
                traceback.print_exc()
                # 오류 발생 시 원본 청크 반환
                return chunk
    
    def generate_markdown_with_claude(self, content, pdf_name, retry_count=0):
        """Claude 3.7 Sonnet 모델을 사용하여 마크다운 생성 (청크 단위 처리)
        
        Args:
            content: 마크다운에 포함될 내용
            pdf_name: PDF 파일명
            retry_count: 재시도 횟수
            
        Returns:
            str: 생성된 마크다운 내용
        """
        try:
            # 내용을 청크로 나누어 처리
            from config import CHUNK_SIZE
            print(f"마크다운 내용을 청크로 분할하여 처리합니다 (청크 크기: {CHUNK_SIZE})...")
            
            # 전체 길이가 3000자 미만인 경우 청크 분할 없이 처리
            if len(content) < 3000:
                print("내용이 짧아 단일 청크로 처리합니다.")
                return self.process_chunk_with_claude(content, pdf_name)
            
            chunks = [content[i:i+CHUNK_SIZE] for i in range(0, len(content), CHUNK_SIZE)]
            print(f"총 {len(chunks)}개의 청크로 분할되었습니다.")
            
            processed_chunks = []
            for i, chunk in enumerate(chunks):
                print(f"청크 {i+1}/{len(chunks)} 처리 중...")
                processed_chunk = self.process_chunk_with_claude(chunk, pdf_name)
                processed_chunks.append(processed_chunk)
                print(f"청크 {i+1} 처리 완료 ({len(processed_chunk)} 글자)")
            
            # 처리된 청크 결합
            final_content = "\n\n".join(processed_chunks)
            print(f"모든 청크 처리 완료 (총 {len(final_content)} 글자)")
            return final_content
            
        except Exception as e:
            if "ThrottlingException" in str(e) and retry_count < MAX_RETRIES:
                print(f"API 호출 제한 오류. {2**retry_count * 3}초 후 재시도... (시도 {retry_count + 1}/{MAX_RETRIES})")
                wait_with_backoff(retry_count)
                return self.generate_markdown_with_claude(content, pdf_name, retry_count + 1)
            else:
                print(f"마크다운 생성 오류: {str(e)}")
                traceback.print_exc()
                return None
