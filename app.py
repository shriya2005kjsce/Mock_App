import streamlit as st
import io
import base64
import json
from datetime import datetime

# Import Firestore client
from google.cloud import firestore

# --- Firestore Client Initialization ---
# This function will initialize the Firestore client and cache it.
# It uses st.secrets to securely access your Firebase service account credentials.
@st.cache_resource
def get_firestore_client():
    try:
        # Load credentials from st.secrets
        key_dict = json.loads(st.secrets["firestore_credentials"])
        db = firestore.Client.from_service_account_info(key_dict)
        st.success("Connected to Firestore!")
        return db
    except Exception as e:
        st.error(f"Error initializing Firestore: {e}. Please check your .streamlit/secrets.toml file.")
        return None

db = get_firestore_client()

# --- App Title and Description ---
st.set_page_config(layout="centered")

st.title("Live Camera Image Storage (Streamlit)")
st.write("Capture photos from your webcam and store them persistently in Firestore.")

# --- User ID Display (Conceptual for multi-user) ---
# In a real multi-user Streamlit app, you'd manage user sessions and IDs
# more robustly, possibly with external authentication.
# For this example, we'll use a placeholder or a simple session ID.
# For Firestore, we'll use a fixed 'default_user' for simplicity,
# but in a production app, you'd generate/retrieve a unique user ID.
if 'user_id' not in st.session_state:
    st.session_state.user_id = "default_user_streamlit" # Using a fixed ID for demo purposes

st.markdown(f"Your User ID for Firestore: `{st.session_state.user_id}`")
st.markdown("---")

# --- Camera Input Section ---
st.header("Capture a Photo")
captured_image_file = st.camera_input("Take a picture")

if captured_image_file:
    st.image(captured_image_file, caption="Captured Image Preview", use_column_width=True)

    if st.button("Save Image to Firestore"):
        if db: # Ensure Firestore client is initialized
            try:
                # Read image bytes
                image_bytes = captured_image_file.getvalue()

                # Convert to Base64 for storage in Firestore
                base64_image = base64.b64encode(image_bytes).decode('utf-8')

                # Define the collection path for public data
                # Using a placeholder app_id as it's not available in Streamlit directly like in Canvas
                app_id_placeholder = "streamlit-camera-app"
                images_collection_ref = db.collection(f"artifacts/{app_id_placeholder}/users/{st.session_state.user_id}/camera_images")

                images_collection_ref.add({
                    'image_b64': base64_image,
                    'timestamp': firestore.SERVER_TIMESTAMP, # Use server timestamp
                    'userId': st.session_state.user_id,
                })
                st.success("Image saved to Firestore!")
            except Exception as e:
                st.error(f"Error saving image to Firestore: {e}")
        else:
            st.warning("Firestore client not initialized. Cannot save image.")

st.markdown("---")

# --- Display Saved Pictures from Firestore ---
st.header("My Saved Pictures (from Firestore)")

if db: # Ensure Firestore client is initialized
    try:
        app_id_placeholder = "streamlit-camera-app"
        images_collection_ref = db.collection(f"artifacts/{app_id_placeholder}/users/{st.session_state.user_id}/camera_images")
        
        # Fetch documents, ordered by timestamp descending
        docs = images_collection_ref.order_by('timestamp', direction=firestore.Query.DESCENDING).stream()
        
        firestore_images = []
        for doc_item in docs: # Renamed 'doc' to 'doc_item' to avoid conflict with 'doc' function
            firestore_images.append({**doc_item.to_dict(), 'id': doc_item.id})

        if firestore_images:
            for i, img_data in enumerate(firestore_images):
                # Display timestamp
                timestamp_str = "Loading..."
                if img_data.get('timestamp'):
                    # Firestore timestamp needs to be converted
                    if isinstance(img_data['timestamp'], datetime):
                        timestamp_str = img_data['timestamp'].strftime('%Y-%m-%d %H:%M:%S')
                    elif hasattr(img_data['timestamp'], 'to_datetime'): # For Firestore Timestamp objects
                        timestamp_str = img_data['timestamp'].to_datetime().strftime('%Y-%m-%d %H:%M:%S')
                    else:
                        timestamp_str = str(img_data['timestamp']) # Fallback for unexpected format

                st.subheader(f"Picture taken on: {timestamp_str}")
                
                # Display image
                st.image(base64.b64decode(img_data['image_b64']), use_column_width=True)

                # Add delete functionality
                if st.button(f"Delete Picture {i+1}", key=f"delete_firestore_{img_data['id']}"):
                    try:
                        db.collection(f"artifacts/{app_id_placeholder}/users/{st.session_state.user_id}/camera_images").document(img_data['id']).delete()
                        st.success("Image deleted from Firestore!")
                        st.experimental_rerun() # Rerun to update the display
                    except Exception as e:
                        st.error(f"Error deleting image from Firestore: {e}")
                st.markdown("---")
        else:
            st.info("No pictures found in Firestore for this user.")
    except Exception as e:
        st.error(f"Error fetching images from Firestore: {e}")
else:
    st.info("Firestore client not initialized. Cannot fetch images.")

