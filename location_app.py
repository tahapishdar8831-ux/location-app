
from flask import Flask, request, render_template_string, jsonify, session
import secrets
import time
import os

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", secrets.token_hex(32))

sessions = {}

HOME = """
<!DOCTYPE html>
<html lang="fa" dir="rtl">
<meta charset="UTF-8">
<title>اشتراک موقعیت</title>
<style>
body {font-family:tahoma;text-align:center;padding:30px}
input,button {padding:12px;margin:8px}
</style>
<h2>پنل اشتراک موقعیت</h2>

<input id="phone" placeholder="شماره موبایل">
<button onclick="createLink()">ساخت لینک</button>

<div id="result"></div>

<script>
async function createLink() {
    const phone = document.getElementById("phone").value.trim();

    if (!/^\\+?[0-9]{8,15}$/.test(phone)) {
        alert("شماره را با کد کشور وارد کن.");
        return;
    }

    const response = await fetch("/create", {
        method: "POST",
        headers: {"Content-Type":"application/json"},
        body: JSON.stringify({phone})
    });

    const data = await response.json();

    const message =
      "سلام. این لینک برای اشتراک‌گذاری موقعیت مکانی است. فقط در صورت رضایت خودت آن را باز کن و اجازه دسترسی به موقعیت را بده: "
      + data.link;

    document.getElementById("result").innerHTML = `
      <p>لینک ساخته شد.</p>
      <p><a href="${data.link}" target="_blank">مشاهده لینک اشتراک</a></p>
      <p><a href="${data.result}" target="_blank">پنل نتیجه</a></p>
      <p><a href="https://t.me/share/url?url=${encodeURIComponent(data.link)}&text=${encodeURIComponent(message)}" target="_blank">ارسال در تلگرام</a></p>
    `;
}
</script>
</html>
"""

SHARE = """
<!DOCTYPE html>
<html lang="fa" dir="rtl">
<meta charset="UTF-8">
<title>اشتراک موقعیت</title>
<body style="font-family:tahoma;text-align:center;padding:30px">
<h2>درخواست اشتراک موقعیت مکانی</h2>
<p>
با تأیید این درخواست، موقعیت مکانی فعلی شما برای درخواست‌کننده ارسال می‌شود.
فقط در صورت رضایت خودتان ادامه دهید.
</p>
<button onclick="share()">تأیید و اشتراک موقعیت</button>
<p id="status"></p>

<script>
function share() {
    const status = document.getElementById("status");

    if (!navigator.geolocation) {
        status.innerText = "مرورگر از موقعیت‌یابی پشتیبانی نمی‌کند.";
        return;
    }

    status.innerText = "منتظر اجازه مرورگر هستیم...";

    navigator.geolocation.getCurrentPosition(async p => {
        const response = await fetch("/send/{{ token }}", {
            method: "POST",
            headers: {"Content-Type":"application/json"},
            body: JSON.stringify({
                lat: p.coords.latitude,
                lon: p.coords.longitude
            })
        });

        status.innerText = response.ok
            ? "موقعیت با موفقیت به اشتراک گذاشته شد."
            : "ارسال موقعیت انجام نشد.";
    }, () => {
        status.innerText = "دسترسی به موقعیت تأیید نشد.";
    });
}
</script>
</body>
</html>
"""

RESULT = """
<!DOCTYPE html>
<html lang="fa" dir="rtl">
<meta charset="UTF-8">
<title>نتیجه</title>
<body style="font-family:tahoma;text-align:center;padding:30px">
<h2>نتیجه اشتراک موقعیت</h2>
{% if data %}
<p>موقعیت با رضایت صاحب گوشی ثبت شده است.</p>
<p>عرض جغرافیایی: {{ data.lat }}</p>
<p>طول جغرافیایی: {{ data.lon }}</p>
<a target="_blank"
href="https://www.openstreetmap.org/?mlat={{ data.lat }}&mlon={{ data.lon }}#map=17/{{ data.lat }}/{{ data.lon }}">
نمایش روی نقشه
</a>
{% else %}
<p>هنوز موقعیتی به اشتراک گذاشته نشده است.</p>
{% endif %}
</body>
</html>
"""

@app.route("/")
def home():
    return render_template_string(HOME)

@app.route("/create", methods=["POST"])
def create():
    if "owner" not in session:
        session["owner"] = secrets.token_urlsafe(32)

    phone = (request.json or {}).get("phone", "")
    if not phone:
        return jsonify({"error":"شماره لازم است"}), 400

    token = secrets.token_urlsafe(24)
    sessions[token] = {
        "data": None,
        "phone": phone,
        "owner": session["owner"],
        "created": time.time()
    }

    base = request.url_root.rstrip("/")
    return jsonify({
        "link": base + "/share/" + token,
        "result": base + "/result/" + token
    })

@app.route("/share/<token>")
def share(token):
    item = sessions.get(token)
    if not item or time.time() - item["created"] > 3600:
        return "لینک منقضی شده است.", 404
    return render_template_string(SHARE, token=token)

@app.route("/send/<token>", methods=["POST"])
def send(token):
    item = sessions.get(token)
    if not item or time.time() - item["created"] > 3600:
        return "لینک منقضی شده است.", 404

    data = request.get_json(silent=True) or {}

    try:
        lat = float(data["lat"])
        lon = float(data["lon"])
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            raise ValueError()
    except (KeyError, TypeError, ValueError):
        return "مختصات نامعتبر است.", 400

    item["data"] = {"lat": lat, "lon": lon}
    return "OK"

@app.route("/result/<token>")
def result(token):
    item = sessions.get(token)

    if not item or time.time() - item["created"] > 3600:
        return "لینک منقضی شده است.", 404

    if session.get("owner") != item["owner"]:
        return "اجازه مشاهده این نتیجه را ندارید.", 403

    return render_template_string(RESULT, data=item["data"])

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
