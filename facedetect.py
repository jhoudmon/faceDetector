import cv2, math, os, tempfile, uuid, subprocess, magic
from naja_atra import request_map, error_message, MultipartFile, StaticFile, Response, PathValue, Redirect, HttpError, server
from datetime import datetime
from mtcnn_cv2 import MTCNN

MINIMUM_WIDTH_FOR_NUMEROTATION = 2400
ALPHA_OVAL = 0.35
detector = MTCNN()


def copy_all_metadata(source_path, target_path):
    subprocess.run([
        "exiftool",
        "-overwrite_original",
        "-TagsFromFile", source_path,
        "-all:all",
        "-unsafe",
        target_path
    ], check=True)


def face_la_plus_proche(faces, faceRef):
    plusProche = min(
        faces,
        key=lambda face: 10000 if face['top'] < faceRef['bottom']
        else math.hypot(face['top'] - faceRef['bottom'], face['left'] - faceRef['left'])
    )
    return None if plusProche['top'] < faceRef['bottom'] else plusProche


def face_la_plus_haute(faces):
    return min(faces, key=lambda face: face['top'])


def number_with_opencv(inputFile, outputFile, increment):
    img = cv2.imread(inputFile, cv2.IMREAD_COLOR)
    if img is None:
        raise RuntimeError("Image illisible")

    resized = False
    if img.shape[1] < MINIMUM_WIDTH_FOR_NUMEROTATION:
        scale = MINIMUM_WIDTH_FOR_NUMEROTATION / img.shape[1]
        img = cv2.resize(
            img,
            (MINIMUM_WIDTH_FOR_NUMEROTATION, int(img.shape[0] * scale)),
            interpolation=cv2.INTER_LINEAR
        )
        resized = True

    rects = detector.detect_faces(img)
    faces = [{'left': x, 'top': y, 'right': x + w, 'bottom': y + h} for r in rects for x, y, w, h in [r['box']]]

    # --- OVALES SUR CALQUE ---
    overlay = img.copy()
    faceNumber = increment

    # Trier visages ligne par ligne (haut -> bas, gauche -> droite)
    faces_work = faces.copy()
    sorted_lines = []
    while faces_work:
        facesRestantes = []
        ligneCourante = []

        faceLaPlusHaute = face_la_plus_haute(faces_work)
        faceLaPlusProche = face_la_plus_proche(faces_work, faceLaPlusHaute)

        for face in faces_work:
            if faceLaPlusProche is None or face['bottom'] <= faceLaPlusProche['top']:
                ligneCourante.append(face)
            else:
                facesRestantes.append(face)

        ligneCourante.sort(key=lambda f: f['left'])
        sorted_lines.append(ligneCourante)
        faces_work = facesRestantes

    # --- DESSIN DES OVALES SUR L'OVERLAY ---
    for ligne in sorted_lines:
        for face in ligne:
            text = str(faceNumber)
            font = cv2.FONT_HERSHEY_SIMPLEX
            thickness = 1
            targetFontHeight = (face['bottom'] - face['top']) / 4
            (stdSize, _) = cv2.getTextSize(text, font, 1, thickness)
            fontScale = targetFontHeight / stdSize[1]

            (tw, th), _ = cv2.getTextSize(text, font, fontScale, thickness)
            rectangleSpace = int((face['bottom'] - face['top']) / 3)
            cx = face['left'] + (face['right'] - face['left']) // 2
            cy = face['bottom'] + rectangleSpace + th // 2
            axes = (tw // 2 + int(tw * 0.35), th // 2 + int(th * 0.45))

            cv2.ellipse(overlay, (cx, cy), axes, 0, 0, 360, (255, 255, 255), -1)
            faceNumber += increment

    # --- FUSION TRANSPARENTE ---
    cv2.addWeighted(overlay, ALPHA_OVAL, img, 1 - ALPHA_OVAL, 0, img)

    # --- TEXTE OPAQUE ---
    faceNumber = increment
    for ligne in sorted_lines:
        for face in ligne:
            text = str(faceNumber)
            font = cv2.FONT_HERSHEY_SIMPLEX
            thickness = 2
            targetFontHeight = (face['bottom'] - face['top']) / 4
            (stdSize, _) = cv2.getTextSize(text, font, 1, thickness)
            fontScale = targetFontHeight / stdSize[1]
            (tw, th), _ = cv2.getTextSize(text, font, fontScale, thickness)
            rectangleSpace = int((face['bottom'] - face['top']) / 3)
            cx = face['left'] + (face['right'] - face['left']) // 2
            cy = face['bottom'] + rectangleSpace + th // 2
            axes = (tw // 2 + int(tw * 0.35), th // 2 + int(th * 0.45))

            cv2.putText(img, text, (cx - tw // 2, cy + th // 2), font, fontScale, (0, 0, 0), thickness, cv2.LINE_AA)

            faceNumber += increment

    cv2.imwrite(outputFile, img)
    copy_all_metadata(inputFile, outputFile)

    # --- METTRE À JOUR EXIF SI REDIMENSIONNÉ ---
    if resized:
        h, w = img.shape[:2]
        subprocess.run([
            "exiftool",
            "-overwrite_original",
            f"-ImageWidth={w}",
            f"-ImageHeight={h}",
            outputFile
        ], check=True)


# ---------------- HTTP ----------------

@request_map("/upload", method="POST")
def upload(increment: str, img=MultipartFile("input")):
    date = datetime.today().strftime('%Y%m%d')
    uuidGenerated = str(uuid.uuid4())
    directoryPath = f'/var/storage/{date[0:4]}/{date[4:6]}/{date[6:8]}'
    os.makedirs(directoryPath, exist_ok=True)

    inputFile = f"{directoryPath}/{uuidGenerated}"
    img.save_to_file(inputFile)

    mime = magic.from_file(inputFile, mime=True)
    if mime not in ['image/jpeg', 'image/png']:
        os.unlink(inputFile)
        raise HttpError(400, "Type MIME non supporté")

    extension = '.jpg' if mime == 'image/jpeg' else '.png'
    os.rename(inputFile, inputFile + extension)

    return Redirect(f"/photo/{uuidGenerated}/{date}/numerotee/{increment}")


@request_map("/photo/{uuid}/{date}/originale")
def downloadOriginale(uuidValue=PathValue("uuid"), date=PathValue("date")):
    base = f"/var/storage/{date[0:4]}/{date[4:6]}/{date[6:8]}/{uuidValue}"
    if os.path.isfile(base + '.png'):
        inputFile = base + '.png'
        contentType = 'image/png'
    elif os.path.isfile(base + '.jpg'):
        inputFile = base + '.jpg'
        contentType = 'image/jpeg'
    else:
        raise HttpError(404, "Photo inexistante")

    with open(inputFile, "rb") as f:
        data = f.read()

    return Response(200, {
        'Content-Type': [contentType],
        'Content-Disposition': [f'inline; filename="{uuidValue}{os.path.splitext(inputFile)[1]}"']
    }, data)


@request_map("/photo/{uuid}/{date}/numerotee/{increment}")
def downloadNumerotee(uuidValue=PathValue("uuid"), date=PathValue("date"), increment=PathValue("increment")):
    base = f"/var/storage/{date[0:4]}/{date[4:6]}/{date[6:8]}/{uuidValue}"
    if os.path.isfile(base + '.png'):
        inputFile = base + '.png'
    elif os.path.isfile(base + '.jpg'):
        inputFile = base + '.jpg'
    else:
        raise HttpError(404, "Photo inexistante")

    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        outputFile = tmp.name

    number_with_opencv(inputFile, outputFile, int(increment))

    with open(outputFile, "rb") as f:
        data = f.read()

    os.unlink(outputFile)

    return Response(200, {
        'Content-Type': ['image/jpeg'],
        'Content-Disposition': [f'inline; filename="{uuidValue}_numerotee_{increment}.jpg"']
    }, data)


@request_map("/", method="GET")
def index():
    root = os.path.dirname(os.path.abspath(__file__))
    return StaticFile(f"{root}/index.html", "text/html; charset=utf-8")


@request_map("/index.js", method="GET")
def indexJS():
    root = os.path.dirname(os.path.abspath(__file__))
    return StaticFile(f"{root}/index.js", "text/javascript; charset=utf-8")


@request_map("/favicon.ico", method="GET")
def favicon():
    root = os.path.dirname(os.path.abspath(__file__))
    return StaticFile(f"{root}/favicon.ico", "image/x-icon")


@error_message("404", "403")
def my_40x_page(code, message, explain=""):
    root = os.path.dirname(os.path.abspath(__file__))
    return StaticFile(f"{root}/error404.html", "text/html; charset=utf-8")


@error_message
def error_message(code, message, explain=""):
    root = os.path.dirname(os.path.abspath(__file__))
    return StaticFile(f"{root}/error.html", "text/html; charset=utf-8")


server.start(port=8000)

#docker build -t facedetector .
#docker run -it --rm --name facedetector -p8000:8000 -v "$PWD":/usr/src/app facedetector
