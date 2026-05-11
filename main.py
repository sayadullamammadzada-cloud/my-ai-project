from flask import Flask, render_template, request, jsonify
import anthropic
import os, base64, json, tempfile

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "gizli-acar-123")

client = anthropic.Anthropic(
    api_key=os.environ.get("ANTHROPIC_API_KEY")
)

def encode_image(path):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")

def convert_heic_to_jpeg(path):
    try:
        from pillow_heif import register_heif_opener
        from PIL import Image
        register_heif_opener()
        img = Image.open(path)
        new_path = path.replace('.heic', '.jpg').replace('.heif', '.jpg')
        img.save(new_path, 'JPEG')
        return new_path
    except:
        return path

def extract_pdf(path):
    try:
        import pdfplumber
        text = ""
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                t = page.extract_text()
                if t:
                    text += t
        if text.strip():
            return text[:4000]
        try:
            from pdf2image import convert_from_path
            import pytesseract
            images = convert_from_path(path)
            ocr = ""
            for img in images:
                ocr += pytesseract.image_to_string(img, lang="aze+eng") + "\n"
            return ocr[:4000] if ocr.strip() else "PDF oxunmadı."
        except:
            return "Skan PDF oxunmadı."
    except Exception as e:
        return f"PDF xətası: {str(e)}"

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/chat", methods=["POST"])
def chat():
    message = request.form.get("message", "")
    history_raw = request.form.get("history", "[]")
    history = json.loads(history_raw)
    files = request.files.getlist("files")

    messages = []
    for h in history:
        messages.append({"role": h["role"], "content": h["content"]})

    content = []
    has_image = False

    for f in files:
        if f.filename == "":
            continue
        ext = f.filename.lower().split(".")[-1]
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=f".{ext}")
        f.save(tmp.name)

        if ext in ["jpg", "jpeg", "png", "webp", "gif", "heic", "heif"]:
            has_image = True
            file_path = tmp.name
            if ext in ["heic", "heif"]:
                file_path = convert_heic_to_jpeg(tmp.name)
            b64 = encode_image(file_path)
            mime = "image/jpeg" if ext in ["jpg", "jpeg", "heic", "heif"] else f"image/{ext}"
            content.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": mime,
                    "data": b64
                }
            })
        elif ext == "pdf":
            text = extract_pdf(tmp.name)
            content.append({"type": "text", "text": f"PDF məzmunu:\n{text}\n\nBu məzmuna əsasən cavab ver."})
        else:
            try:
                with open(tmp.name, "r", errors="ignore") as fp:
                    text = fp.read()[:4000]
                content.append({"type": "text", "text": f"Fayl məzmunu:\n{text}"})
            except:
                pass

    if message:
        content.append({"type": "text", "text": message})

    if not content:
        return jsonify({"response": "Mesaj və ya fayl göndərin."})

    if len(content) == 1 and content[0]["type"] == "text":
        messages.append({"role": "user", "content": content[0]["text"]})
    else:
        messages.append({"role": "user", "content": content})

    try:
        response = client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=1024,
            system="Sən AI-Tech-In köməkçisisən. Həmişə Azərbaycan dilində cavab ver. İstifadəçi ingilis yazsa ingilis cavab ver. Türkcə cavab vermə.",
            messages=messages
        )
        return jsonify({"response": response.content[0].text})
    except Exception as e:
        return jsonify({"response": f"Xəta: {str(e)}"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
