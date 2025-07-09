import streamlit as st
import io
import base64
from datetime import datetime

# --- Configuration for Firestore (Conceptual - for actual deployment) ---
# To connect to Firestore in a deployed Streamlit app (e.g., Streamlit Cloud):
# 1. Go to your Firebase project settings -> Service accounts.
# 2. Generate a new private key and download the JSON file.
# 3. In your Streamlit app's secrets (e.g., .streamlit/secrets.toml), add the content
#    of this JSON file under a key like 'firestore_credentials'.
# 4. Then, you would use the google-cloud-firestore library like this:
#
# from google.cloud import firestore
#
# @st.cache_resource
# def get_firestore_client():
#     # Initialize Firestore DB client using credentials from st.secrets
#     # This assumes you've saved your service account key in st.secrets.toml
#     # under a key like 'firestore_credentials'
#     try:
#         key_dict = json.loads(st.secrets["firestore_credentials"])
#         db = firestore.Client.from_service_account_info(key_dict)
#         return db
#     except Exception as e:
#         st.error(f"Error initializing Firestore: {e}")
#         return None
#
# db = get_firestore_client()
#
# For this demonstration, we will use st.session_state for temporary storage.

# --- App Title and Description ---
st.set_page_config(layout="centered")

st.title("Live Camera Image Storage (Streamlit)")
st.write("Capture photos from your webcam and see them displayed below.")
st.write("Note: For persistent storage in a deployed app, you would integrate with a database like Firestore.")

# --- User ID Display (Conceptual for multi-user) ---
# In a real multi-user Streamlit app, you'd manage user sessions and IDs
# more robustly, possibly with external authentication.
# For this example, we'll use a placeholder or a simple session ID.
if 'user_id' not in st.session_state:
    st.session_state.user_id = "user_" + base64.urlsafe_b64encode(io.BytesIO(str(datetime.now()).encode()).read()).decode()[:8]

st.markdown(f"Your (temporary) User ID: `{st.session_state.user_id}`")
st.markdown("*(This ID is unique to your current session and for demonstration purposes only.)*")

st.markdown("---")

# --- Camera Input Section ---
st.header("Capture a Photo")
captured_image_file = st.camera_input("Take a picture")

if captured_image_file:
    st.image(captured_image_file, caption="Captured Image Preview", use_column_width=True)

    if st.button("Save Image (Temporary Session Storage)"):
        # Read image bytes
        image_bytes = captured_image_file.getvalue()

        # Convert to Base64 for easier storage if needed (e.g., in a JSON-compatible DB field)
        # For direct file storage, you might upload bytes to cloud storage (e.g., S3, GCS)
        base64_image = base64.b64encode(image_bytes).decode('utf-8')

        # Store in session state (temporary)
        if 'saved_images' not in st.session_state:
            st.session_state.saved_images = []

        st.session_state.saved_images.append({
            'id': str(datetime.now().timestamp()), # Unique ID for this image
            'image_b64': base64_image,
            'timestamp': datetime.now().isoformat()
        })
        st.success("Image saved to session!")

        # --- Firestore Integration (Conceptual - for actual deployment) ---
        # if db: # If Firestore client is initialized
        #     try:
        #         images_collection_ref = db.collection(f"artifacts/{st.session_state.app_id}/users/{st.session_state.user_id}/camera_images")
        #         images_collection_ref.add({
        #             'image_b64': base64_image,
        #             'timestamp': firestore.SERVER_TIMESTAMP,
        #             'userId': st.session_state.user_id,
        #         })
        #         st.success("Image saved to Firestore!")
        #     except Exception as e:
        #         st.error(f"Error saving image to Firestore: {e}")
        # else:
        #     st.warning("Firestore client not initialized. Image saved to session only.")

st.markdown("---")

# --- Display Saved Pictures ---
st.header("My Saved Pictures (Current Session)")

if 'saved_images' in st.session_state and st.session_state.saved_images:
    # Display images in reverse order (most recent first)
    for i, img_data in enumerate(reversed(st.session_state.saved_images)):
        st.subheader(f"Picture taken on: {datetime.fromisoformat(img_data['timestamp']).strftime('%Y-%m-%d %H:%M:%S')}")
        st.image(base64.b64decode(img_data['image_b64']), use_column_width=True)

        if st.button(f"Delete Picture {i+1}", key=f"delete_{img_data['id']}"):
            # Remove from session state
            st.session_state.saved_images = [
                img for img in st.session_state.saved_images if img['id'] != img_data['id']
            ]
            st.success("Image deleted from session!")
            st.experimental_rerun() # Rerun to update the display

        st.markdown("---")
else:
    st.info("No pictures saved in this session yet.")

# --- Firestore Display (Conceptual - for actual deployment) ---
# if db:
#     st.header("My Saved Pictures (from Firestore)")
#     try:
#         images_collection_ref = db.collection(f"artifacts/{st.session_state.app_id}/users/{st.session_state.user_id}/camera_images")
#         docs = images_collection_ref.order_by('timestamp', direction=firestore.Query.DESCENDING).stream()
#         firestore_images = []
#         for doc in docs:
#             firestore_images.append(doc.to_dict())
#
#         if firestore_images:
#             for img_data in firestore_images:
#                 st.subheader(f"Picture taken on: {img_data['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}")
#                 st.image(base64.b64decode(img_data['image_b64']), use_column_width=True)
#                 # Add delete functionality for Firestore images too
#                 # This would involve calling a delete function that uses db.collection(...).document(...).delete()
#                 st.markdown("---")
#         else:
#             st.info("No pictures found in Firestore for this user.")
#     except Exception as e:
#         st.error(f"Error fetching images from Firestore: {e}")
