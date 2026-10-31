import asyncio
import os
from io import BytesIO
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel, Field
import edge_tts

app = FastAPI(title='Text to Voice Studio')
VOICE_MAP = {
    'th-female': 'th-TH-PremwadeeNeural',
    'th-male': 'th-TH-NiwatNeural',
    'en-female': 'en-US-JennyNeural',
    'en-male': 'en-US-GuyNeural',
    'zh-female': 'zh-CN-XiaoxiaoNeural',
    'zh-male': 'zh-CN-YunxiNeural',
}

class TTSRequest(BaseModel):
    text: str = Field(min_length=1, max_length=5000)
    language: str = 'th'
    gender: str = 'female'
    speed: int = Field(default=0, ge=-50, le=50)

PAGE_HTML = '<!doctype html>\n<html lang="th"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"><meta name="theme-color" content="#0f172a"><title>Text to Voice Studio</title><style>\n*{box-sizing:border-box}body{margin:0;background:#f3f6fb;color:#17243b;font-family:system-ui,-apple-system,\'Segoe UI\',sans-serif}.wrap{max-width:650px;margin:0 auto;padding:22px 16px 60px}header{background:#0f172a;color:white;padding:26px;border-radius:20px;margin-bottom:18px}h1{font-size:25px;margin:0 0 7px}p{margin:0;line-height:1.6}header p{color:#b6c7e7}.card{background:white;padding:21px;border-radius:18px;box-shadow:0 8px 30px #17243b0b}.field{margin-bottom:19px}label{display:block;font-weight:650;margin-bottom:9px}textarea,select,input[type=range]{width:100%}textarea,select{border:1px solid #ccd5e2;border-radius:12px;padding:13px;font:inherit;background:white}textarea{min-height:170px;resize:vertical}select{height:48px}.split{display:grid;grid-template-columns:1fr 1fr;gap:12px}.count{font-size:12px;color:#68758b;text-align:right;margin-top:5px}button{background:#2563eb;color:#fff;border:0;padding:15px 18px;border-radius:13px;font:inherit;font-weight:700;width:100%;cursor:pointer}button:disabled{opacity:.55;cursor:wait}.download{display:none;text-align:center;padding:15px;border-radius:13px;background:#0f766e;color:white;font-weight:700;text-decoration:none;margin-top:12px}audio{width:100%;margin-top:15px;display:none}.status{font-size:14px;min-height:22px;margin:14px 0 0;color:#53647d}.note{font-size:13px;color:#627188;line-height:1.7;margin-top:17px}.small{font-size:14px;color:#475569}@media(max-width:390px){.split{grid-template-columns:1fr}}\n</style></head><body><div class="wrap"><header><h1>🎙️ Text to Voice Studio</h1><p>แปลงสคริปต์เป็นเสียงพูด • ฟังตัวอย่าง • ดาวน์โหลด MP3 จาก iPhone</p></header><main class="card"><div class="field"><label for="script">สคริปต์ข้อความ</label><textarea id="script" maxlength="5000" placeholder="พิมพ์หรือวางข้อความที่ต้องการทำเป็นเสียงพูด...">สวัสดีครับ ยินดีต้อนรับเข้าสู่โปรแกรมแปลงข้อความเป็นเสียงพูด</textarea><div class="count" id="count">0 / 5000</div></div><div class="split"><div class="field"><label for="language">ภาษา</label><select id="language"><option value="th">🇹🇭 ภาษาไทย</option><option value="en">🇺🇸 English</option><option value="zh">🇨🇳 中文</option></select></div><div class="field"><label for="gender">เสียงพูด</label><select id="gender"><option value="female">ผู้หญิง</option><option value="male">ผู้ชาย</option></select></div></div><div class="field"><label for="speed">ความเร็ว <span id="speedValue">ปกติ</span></label><input type="range" min="-50" max="50" step="5" value="0" id="speed"></div><button type="button" id="generate">สร้างคลิปเสียง MP3</button><div class="status" id="status" aria-live="polite"></div><audio id="player" controls playsinline></audio><a class="download" id="download" href="#" download="voice-studio.mp3">⬇ ดาวน์โหลดเสียง MP3</a><p class="note">การสร้างเสียงต้องเชื่อมต่ออินเทอร์เน็ต เว็บไซต์ส่งข้อความไปยังบริการสังเคราะห์เสียงภายนอก ไม่ควรใส่ข้อมูลลับ</p></main><p class="small" style="margin-top:18px">บน iPhone: เมื่อกดดาวน์โหลดแล้ว สามารถบันทึกไฟล์ในแอป Files หรือใช้ปุ่มแชร์เพื่อ “Save to Files” ได้</p></div><script>\nconst $=id=>document.getElementById(id);let current=null;const txt=$(\'script\');function count(){ $(\'count\').textContent=txt.value.length+\' / 5000\' }txt.addEventListener(\'input\',count);count();$(\'speed\').addEventListener(\'input\',()=>{$(\'speedValue\').textContent=$(\'speed\').value==0?\'ปกติ\':$(\'speed\').value+\'%\' });$(\'generate\').addEventListener(\'click\',async()=>{const text=txt.value.trim();if(!text){$(\'status\').textContent=\'กรุณาใส่ข้อความก่อน\';return}const button=$(\'generate\');button.disabled=true;$(\'status\').textContent=\'กำลังสร้างคลิปเสียง...\';$(\'download\').style.display=\'none\';$(\'player\').style.display=\'none\';try{const res=await fetch(\'/api/tts\',{method:\'POST\',headers:{\'Content-Type\':\'application/json\'},body:JSON.stringify({text,language:$(\'language\').value,gender:$(\'gender\').value,speed:Number($(\'speed\').value)})});if(!res.ok)throw new Error(\'ไม่สามารถสร้างเสียงได้ กรุณาลองใหม่\');const blob=await res.blob();if(!blob.size)throw new Error(\'ไฟล์เสียงว่าง\');if(current)URL.revokeObjectURL(current);current=URL.createObjectURL(blob);$(\'player\').src=current;$(\'player\').style.display=\'block\';$(\'download\').href=current;$(\'download\').style.display=\'block\';$(\'status\').textContent=\'สร้างเสียงสำเร็จ — ฟังตัวอย่างหรือดาวน์โหลด MP3 ได้\';}catch(e){$(\'status\').textContent=e.message}finally{button.disabled=false}});\n</script></body></html>\n'

@app.get('/', response_class=HTMLResponse)
def index():
    return PAGE_HTML

@app.get('/health')
def health():
    return {'ok': True}

@app.post('/api/tts')
async def make_audio(req: TTSRequest):
    key = f'{req.language}-{req.gender}'
    if key not in VOICE_MAP or not req.text.strip():
        raise HTTPException(status_code=400, detail='Invalid voice or text')
    rate = f'{req.speed:+d}%'
    try:
        audio = bytearray()
        async for item in edge_tts.Communicate(req.text.strip(), VOICE_MAP[key], rate=rate).stream():
            if item['type'] == 'audio':
                audio.extend(item['data'])
        if not audio:
            raise RuntimeError('No audio returned')
        return StreamingResponse(BytesIO(audio), media_type='audio/mpeg', headers={
            'Content-Disposition': 'attachment; filename="voice-studio.mp3"',
            'Cache-Control':'no-store',
        })
    except Exception:
        raise HTTPException(status_code=502, detail='Unable to generate audio. Please try again later.')
