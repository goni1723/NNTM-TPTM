import os
import time
import cv2
import numpy as np
import traceback
from ultralytics import YOLO
from flask import Flask, Response, render_template, request, jsonify
import pandas as pd
import requests
from werkzeug.utils import secure_filename

app = Flask(__name__)

UPLOAD_FOLDER = 'uploaded_videos'
ALLOWED_EXTENSIONS = {'mp4', 'avi', 'mov', 'mkv'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

line_pts = []
track_history = {}
frame_count = 0
first_frame = None
processing_started = False
violations = []
current_video = None

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/upload_video', methods=['POST'])
def upload_video():
    global current_video, first_frame
    if 'video' not in request.files:
        return jsonify({'error': 'Không tìm thấy file'}), 400
    
    file = request.files['video']
    if file.filename == '':
        return jsonify({'error': 'Không có file nào được chọn'}), 400
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        current_video = filepath
        
        cap = cv2.VideoCapture(current_video)
        ret, first_frame = cap.read()
        cap.release()
        if not ret:
            return jsonify({'error': 'Không thể đọc video'}), 400
        
        return jsonify({'success': True, 'message': 'Video đã được tải lên thành công'})
    return jsonify({'error': 'File không được phép'}), 400

car_model = YOLO(r'C:\Users\Admin\Downloads\Smart-City-and-Smart-Agriculture-main\Smart-City-and-Smart-Agriculture-main\Smart_City-Case_study\yolov8n.pt')
tl_model = YOLO(r'C:\Users\Admin\Downloads\Smart-City-and-Smart-Agriculture-main\Smart-City-and-Smart-Agriculture-main\Smart_City-Case_study\best_traffic_nano_yolo.pt')
os.makedirs('vi_pham', exist_ok=True)

def side_of_line(pt, p1, p2):
    x1, y1 = p1
    x2, y2 = p2
    return (x2 - x1) * (pt[1] - y1) - (y2 - y1) * (pt[0] - x1)

def export_to_csv(violations_data, filename='bao_cao_vi_pham.csv'):
    df = pd.DataFrame(violations_data, columns=['ID Xe', 'Thời gian vi phạm', 'Đường dẫn ảnh'])
    df.to_csv(filename, index=False, encoding='utf-8')
    print(f"[THÔNG BÁO] Đã xuất báo cáo ra {filename}")
    return filename

def send_message_to_telegram(message, bot_token, chat_id):
    try:
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        data = {'chat_id': chat_id, 'text': message}
        response = requests.post(url, data=data)
        if response.status_code == 200:
            print(f"[THÔNG BÁO] Đã gửi tin nhắn thử qua Telegram: {message}")
        else:
            print(f"[LỖI] Gửi tin nhắn thử qua Telegram thất bại: {response.text}")
    except Exception as e:
        print(f"[LỖI] Gửi tin nhắn thử qua Telegram thất bại: {e}")



@app.route('/first_frame')
def get_first_frame():
    ret, buffer = cv2.imencode('.jpg', first_frame)
    frame = buffer.tobytes()
    return Response(frame, mimetype='image/jpeg')

@app.route('/set_line_points', methods=['POST'])
def set_line_points():
    global line_pts, processing_started
    data = request.get_json()
    x1 = int(data['x1'])
    y1 = int(data['y1'])
    x2 = int(data['x2'])
    y2 = int(data['y2'])
    line_pts = [(x1, y1), (x2, y2)]
    print(f"[DEBUG] line_pts: {line_pts}")
    processing_started = True
    return jsonify({"status": "success", "message": "Đã thiết lập tọa độ đường thẳng thành công"})

@app.route('/violations', methods=['GET'])
def get_violations():
    return jsonify(violations)

def generate_frames():
    global frame_count, track_history, violations, current_video
    if not processing_started or current_video is None:
        return

    cap = cv2.VideoCapture(current_video)
    fps = cap.get(cv2.CAP_PROP_FPS)
    cap.release()

    frame_delay = 1.0 / fps if fps > 0 else 1.0 / 30.0

    track_stream = car_model.track(
        source=current_video,
        conf=0.5,
        iou=0.5,
        persist=True,
        stream=True
    )

    bot_token = "YOUR_BOT_TOKEN"
    chat_id = "YOUR_CHAT_ID"
    send_message_to_telegram("Hệ thống bắt đầu xử lý video để phát hiện vi phạm.", bot_token, chat_id)

    for result in track_stream:
        try:
            frame_count += 1
            frame = result.orig_img.copy()

            if len(line_pts) == 2:
                pt1, pt2 = line_pts
                cv2.line(frame, pt1, pt2, (0, 255, 0), 2)

            tl_res = tl_model(frame, conf=0.3)[0]
            tl_state = None
            for tl_box in tl_res.boxes:
                x1_l, y1_l, x2_l, y2_l = tl_box.xyxy.cpu().numpy().astype(int)[0]
                cls_id = int(tl_box.cls.cpu().item())
                conf_l = float(tl_box.conf.cpu().item())
                name = tl_model.model.names[cls_id]
                color = (0, 255, 0) if name == 'green' else (0, 0, 255) if name == 'red' else (255, 255, 0)
                cv2.rectangle(frame, (x1_l, y1_l), (x2_l, y2_l), color, 2)
                cv2.putText(frame, f"{name}:{conf_l:.2f}", (x1_l, y1_l - 5),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
                if tl_state is None or conf_l > tl_state[1]:
                    tl_state = (name, conf_l)

            light_label = tl_state[0] if tl_state else "no-light"
            cv2.putText(frame, f"Đèn: {light_label}", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 1,
                        (0, 255, 0) if light_label == 'green' else (0, 0, 255), 2)

            for box in result.boxes:
                if box.id is None:
                    continue
                tid = int(box.id.cpu().item())
                x1, y1, x2, y2 = box.xyxy.cpu().numpy().astype(int)[0]
                cx = (x1 + x2) // 2
                cy = y2

                if tid not in track_history:
                    track_history[tid] = {
                        'pt': (cx, cy),
                        'crossed': False,
                        'violation': False,
                        'violation_time': None
                    }
                rec = track_history[tid]

                box_color = (0, 0, 255) if rec['violation'] else (255, 0, 0)

                if not rec['crossed'] and len(line_pts) == 2:
                    s_prev = side_of_line(rec['pt'], line_pts[0], line_pts[1])
                    s_curr = side_of_line((cx, cy), line_pts[0], line_pts[1])
                    if s_prev * s_curr < 0:
                        if light_label == 'red':
                            rec['violation'] = True
                            rec['violation_time'] = time.time()
                            crop = result.orig_img[y1:y2, x1:x2]
                            fname = os.path.join('vi_pham', f"car_{tid}_{frame_count}.jpg")
                            cv2.imwrite(fname, crop)
                            print(f"[VI PHẠM] Đã lưu {fname}")
                            violation_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
                            violations.append([tid, violation_time, fname])
                        rec['crossed'] = True

                rec['pt'] = (cx, cy)

                cv2.rectangle(frame, (x1, y1), (x2, y2), box_color, 2)
                cv2.putText(frame, f"ID:{tid}", (x1, y1 - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, box_color, 2)
                cv2.circle(frame, (cx, cy), 4, box_color, -1)

                if rec['violation'] and rec['violation_time'] is not None:
                    if time.time() - rec['violation_time'] <= 1.0:
                        cv2.putText(frame, "VI PHẠM", (x1, y1 - 30),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)

            violation_count = sum(1 for v in track_history.values() if v['violation'])
            cv2.putText(frame, f"Số vi phạm: {violation_count}", (10, 60),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)

            ret, buffer = cv2.imencode('.jpg', frame)
            frame = buffer.tobytes()
            time.sleep(frame_delay)
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

        except Exception as e:
            print(f"[CẢNH BÁO] Bỏ qua khung hình do lỗi: {e}")
            traceback.print_exc()
            continue

    if violations:
        report_file = export_to_csv(violations)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
