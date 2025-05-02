"""
Amazon Bedrock 모델 호출에 사용되는 프롬프트 상수 모음
"""

# 도면 분석 프롬프트 - Nova Premier 모델용
DRAWING_ANALYSIS_PROMPT = """
Carefully analyze the drawings and provide the following information:

1. Drawing type: Identify the type of drawing (architectural, mechanical, electrical, plumbing, etc.); retain the original language when translating.
2. Major components: Identify the major components shown in the drawings.
3. Numerical values and dimensions: Accurately record all numerical values and dimensions shown in the drawings.
   - Clearly indicate the value and unit of all dimensions
- Classify dimensions such as length, width, height, diameter, and radius systematically
4. Annotations and special symbols: Include the meaning of annotations and special symbols indicated on the drawing
5. Coordinates and orientation: If coordinates or orientation are indicated on the drawing, specify them
6. Record content that is a combination of numbers, characters, and special symbols.
7. If there are notes in the drawing, record the note contents in detail (e.g., nozzle data description, etc.)
8. Table format information: Data presented in tables should be organized in table format  
   - Clearly distinguish each column and row in the table  
   - Convert the table headers and data to JSON format  
   - Clearly distinguish each cell in the table
   - Clearly distinguish each column and row of the table
9. Record all text within the drawing in the original language, and provide both the original and translation if translation is required

Return format:
- Structure the analysis results in JSON format.
- Accurately write table data in JSON key-value format.
- Record numbers and units accurately, and group them by category if possible.
- At the end, add numerical data in a JSON block in the following format:

```json
{
  “drawing_type”: “drawing type”,
  “key_dimensions”: [
    {“component”: “component1”, “dimension”: “dimension1”, “value”: value, “unit”: “unit”},
    {“component”: “Component2”, “dimension”: “Dimension2”, “value”: value, “unit”: “Unit”}
  ],
  “coordinates”: {
    “system”: “Coordinate system type”,
    “orientation”: “Orientation information”
  }
}
```
"""

# 도면 식별 프롬프트 - Nova Lite 모델용
DRAWING_IDENTIFICATION_PROMPT = """이 이미지가 기술 도면, 건축 도면, 설계 도면인지 판단해주세요.
이미지에 직선, 도형, 치수, 기술적 표기가 많고 텍스트가 적으면 도면일 가능성이 높습니다. 페이지에 테이블 정보만 있다면 이것도 도면으로 간주하세요.
도면이면 "YES"만 답변하고, 도면이 아니면 "NO"만 답변해주세요."""

# 마크다운 청크 처리 프롬프트 - Claude 모델용
def get_markdown_processing_prompt(pdf_name, chunk):
    return f"""
당신은 PDF 문서의 원본 내용을 유지하면서 도면 이미지 및 분석 결과를 통합하는 전문가입니다.
"{pdf_name}" 문서의 마크다운 내용을 유지하면서 도면 이미지와 분석 결과를 적절히 표시해주세요.
이 내용은 전체 문서의 일부분입니다.

절대적으로 지켜야 할 규칙:
1. 제공된 원본 마크다운 내용을 최대한 보존하세요.
2. 도면 이미지와 분석 결과가 이미 마크다운에 삽입되어 있으면, 이 형식을 그대로 유지하세요.
3. 도면이 없는 경우에도 원본 PDF 내용을 보존하세요.
4. 이미지 참조 형식(![도면 이미지](경로))을 정확히 유지하세요.
5. 도면 분석에 있는 표 형식을 유지하세요. JSON 데이터를 해석해서 표 형식으로 변환하세요.
   - 표의 각 열과 행을 명확히 구분하세요.
   - 표의 헤더와 데이터를 JSON 형식으로 변환하세요.
   - 표의 각 셀을 명확히 구분하세요.
   - 표의 각 열과 행을 명확히 구분하세요.
6. 페이지 구분자(<!-- page X -->)를 보존하세요.
7. 문서 전체적으로 일관된 헤더 수준을 유지하세요.
8. 실제 내용이 없는 빈 섹션이나 "내용이 제공되지 않았습니다"와 같은 텍스트를 제거하세요.
9. 청크의 시작과 끝이 문장 중간에 끊길 수 있으므로 불완전한 문장은 그대로 유지하세요.
10. 내용이 없는 공백 페이지의 경우에도 페이지 구분자를 유지하세요.

원본 마크다운 내용:
```
{chunk}
```

작업할 마크다운을 제공해주세요. "다음과 같이 정리했습니다"와 같은 안내 문구 없이 바로 마크다운 내용을 시작하세요.
"""
