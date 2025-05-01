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
from prompts import (
    DRAWING_ANALYSIS_PROMPT,
    DRAWING_IDENTIFICATION_PROMPT,
    get_markdown_processing_prompt
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
            prompt = DRAWING_ANALYSIS_PROMPT
            
            # 컨텍스트 정보가 있으면 프롬프트에 추가
            if context:
                prompt += f"\n\n관련 컨텍스트 정보:\n{context}"
            
            # Nova Premier 모델 초기화
            chat = ChatBedrock(
                model_id=BEDROCK_NOVA_PRO_MODEL_ID,
                region_name=BEDROCK_REGION,
                model_kwargs={
                    "temperature": 0.0,
                    "top_p": 0.0,
                    "top_k": 0,
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
            prompt = DRAWING_ANALYSIS_PROMPT
            
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
                    "top_p": 0.0,
                    "top_k": 0,
                    "maxTokens": 10
                }
            )
            
            # 멀티모달 메시지 구성
            message = HumanMessage(
                content=[
                    {
                        "type": "text", 
                        "text": DRAWING_IDENTIFICATION_PROMPT
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
            prompt = DRAWING_IDENTIFICATION_PROMPT
            
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
                    "temperature": 0.0,
                    "topP": 0.0,
                    "topK": 0
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
            prompt = get_markdown_processing_prompt(pdf_name, chunk)
            
            # API 요청 구성
            body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 4000,
                "temperature": 0.0,
                "top_p": 0.0,
                "top_k": 0,
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
