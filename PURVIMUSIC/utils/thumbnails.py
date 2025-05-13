import os,aiofiles,aiohttp,asyncio
from PIL import Image,ImageDraw,ImageFont,ImageFilter,ImageEnhance
from youtubesearchpython.__future__ import VideosSearch
async def fetch_with_retry(s,u,r=3):
 for _ in range(r):
  try:
   async with s.get(u,timeout=5)as x:
    if x.status==200:return await x.read()
  except:pass
  await asyncio.sleep(0.001)
async def get_youtube_metadata(v):
 try:
  u=f"https://www.youtube.com/watch?v={v}"
  r=await VideosSearch(u,limit=1).next()
  return r["result"][0] if r and"result"in r else None
 except:
  return None
def create_gradient(z):
 g=Image.new("RGBA",z)
 d=ImageDraw.Draw(g)
 for y in range(z[1]):
  t=y/z[1];a=int(90*(1-t)+180*t)
  d.line([(0,y),(z[0],y)],fill=(0,0,0,a))
 return g
def truncate_text(d,t,f,w):
 if d.textlength(t,font=f)<=w:return t
 while t and d.textlength(t+"...",font=f)>w:t=t[:-1]
 return t+"..."if t else""
async def get_thumb(v):
 if not isinstance(v,str)or not v:
  return f"https://i.ytimg.com/vi/{v}/maxresdefault.jpg"
 os.makedirs("cache",exist_ok=True)
 p=f"cache/{v}.png";t=f"cache/temp_{v}.png"
 if os.path.isfile(p):os.remove(p)
 d=await get_youtube_metadata(v)
 if not d:
  return f"https://i.ytimg.com/vi/{v}/maxresdefault.jpg"
 h=d.get("thumbnails",[])
 u=next((x["url"].split("?")[0]for x in h if x["url"].split("?")[0].endswith("maxresdefault.jpg")),h[0]["url"].split("?")[0]if h else f"https://i.ytimg.com/vi/{v}/maxresdefault.jpg")
 n=d.get("title","Unknown Title")
 c=d.get("channel",{}).get("name","Unknown Channel")
 async with aiohttp.ClientSession()as s:
  i=await fetch_with_retry(s,u)
  if not i:
   return f"https://i.ytimg.com/vi/{v}/maxresdefault.jpg"
  async with aiofiles.open(t,"wb")as f:
   await f.write(i)
 try:
  m=Image.open(t).resize((1280,720),Image.Resampling.LANCZOS).filter(ImageFilter.GaussianBlur(15)).convert("RGBA")
  m=ImageEnhance.Brightness(m).enhance(1.3)
  m=ImageEnhance.Contrast(m).enhance(1.3)
  m=ImageEnhance.Color(m).enhance(1.2)
  m=Image.alpha_composite(m,create_gradient((1280,720)))
 except:
  if os.path.exists(t):os.remove(t)
  return f"https://i.ytimg.com/vi/{v}/maxresdefault.jpg"
 a=Image.new("RGBA",(600,420),(0,0,0,0))
 d=ImageDraw.Draw(a)
 d.rounded_rectangle([(0,0),(600,420)],30,(0,0,0,190))
 try:
  b=Image.open(t).resize((184,184),Image.Resampling.LANCZOS).convert("RGBA")
  b=ImageEnhance.Sharpness(b).enhance(1.5)
  k=Image.new("L",(184,184),0)
  ImageDraw.Draw(k).rounded_rectangle([(0,0),(184,184)],15,255)
  b.putalpha(k)
  a.paste(b,(30,(420-184-164-15)//2),b)
 except:
  if os.path.exists(t):os.remove(t)
  return f"https://i.ytimg.com/vi/{v}/maxresdefault.jpg"
 r="PURVIMUSIC/assets/controller.png"
 if os.path.exists(r):
  e=Image.open(r).convert("RGBA").resize((550,148),Image.Resampling.LANCZOS)
  e=ImageEnhance.Sharpness(e).enhance(2.0)
  a.paste(e,((600-550)//2,420-148-15),e)
 f="PURVIMUSIC/assets/font.ttf"
 try:
  l=ImageFont.truetype(f,28)
  o=ImageFont.truetype(f,16)
  w=ImageFont.truetype(f,14)
 except:
  l=o=w=ImageFont.load_default()
 x=234;y=(420-184-164-15)//2+10
 d.text((x,y+40),c,(192,192,192,255),o)
 d.text((x,y+70),truncate_text(d,n,l,360),(255,255,255,255),l)
 m.paste(a,((1280-600)//2,(720-420)//2),a)
 d=ImageDraw.Draw(m)
 q="Powered By System"
 z=d.textlength(q,w)
 d.text((1280-z-20,20),q,(192,192,192,255),w)
 try:
  m.save(p,"PNG",quality=100)
 except:
  if os.path.exists(t):os.remove(t)
  return f"https://i.ytimg.com/vi/{v}/maxresdefault.jpg"
 if os.path.exists(t):os.remove(t)
 return p if os.path.exists(p)else f"https://i.ytimg.com/vi/{v}/maxresdefault.jpg"
