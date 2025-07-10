import os
import cv2
import json
import face_recognition
import chromadb
import numpy as np

UPLOAD_FOLDER = 'uploads'
USER_DATA_FILE = 'user_data.json'

chroma_client = chromadb.PersistentClient(path="chroma_db")
collection = chroma_client.get_or_create_collection(name="face_encodings")


def encode_and_store_faces():
    print(" Syncing ChromaDB with JSON + uploads folder...")

    # Load valid user IDs from JSON
    if os.path.exists(USER_DATA_FILE):
        with open(USER_DATA_FILE, 'r') as f:
            user_data = json.load(f)
    else:
        user_data = {}

    valid_user_ids = set(user_data.keys())

    # Remove ChromaDB embeddings for IDs not in valid_user_ids
    existing_ids = set(collection.get()['ids'])
    extra_ids = existing_ids - valid_user_ids

    if extra_ids:
        collection.delete(ids=list(extra_ids))

    # Step 3: Add or update valid encodings
    for user_id in valid_user_ids:
        img_path = os.path.join(UPLOAD_FOLDER, f"{user_id}.png")

        if not os.path.exists(img_path):
            continue

        img = cv2.imread(img_path)
        if img is None:
            continue

        rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        boxes = face_recognition.face_locations(rgb)
        encodings = face_recognition.face_encodings(rgb, boxes)

        if not encodings:
            continue

        embedding = encodings[0].tolist()

        if user_id in existing_ids:
            collection.delete(ids=[user_id])

        collection.add(
            ids=[user_id],
            embeddings=[embedding],
            metadatas=[{"user_id": user_id, "user_name": user_data[user_id]}]
        )

    print(" Done syncing ChromaDB.")
