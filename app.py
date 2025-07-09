import streamlit as st
import io
import base64
import pandas as pd
import json
from datetime import datetime

# Import Google Cloud Storage client
from google.cloud import storage

# --- GCS Client Initialization ---
@st.cache_resource
def get_gcs_client():
    try:
        # Load credentials from st.secrets
        key_dict = json.loads(st.secrets["gcs_credentials"])
        client = storage.Client.from_service_account_info(key_dict)
        st.success("Connected to Google Cloud Storage!")
        return client
    except Exception as e:
        st.error(f"Error initializing GCS client: {e}. Please check your .streamlit/secrets.toml file.")
        return None

gcs_client = get_gcs_client()
gcs_bucket_name = st.secrets.get("gcs_bucket_name")
gcs_csv_filename = "images_data.csv" # The name of the CSV file in your GCS bucket

# --- Functions for GCS CSV Operations ---

def load_images_from_gcs_csv(client, bucket_name, filename):
    """Loads image data from a CSV file in GCS into a DataFrame."""
    if not client or not bucket_name:
        return pd.DataFrame(columns=['id', 'timestamp', 'image_b64'])

    try:
        bucket = client.get_bucket(bucket_name)
        blob = bucket.blob(filename)
        
        if blob.exists():
            csv_bytes = blob.download_as_bytes()
            df = pd.read_csv(io.BytesIO(csv_bytes))
            st.info(f"Loaded {len(df)} images from GCS.")
            return df
        else:
            st.info("No existing image data CSV found in GCS. Starting fresh.")
            return pd.DataFrame(columns=['id', 'timestamp', 'image_b64'])
    except Exception as e:
        st.error(f"Error loading images from GCS CSV: {e}")
        return pd.DataFrame(columns=['id', 'timestamp', 'image_b64'])

def save_images_to_gcs_csv(client, bucket_name, filename, dataframe):
    """Saves DataFrame containing image data to a CSV file in GCS."""
    if not client or not bucket_name:
        st.error("GCS client or bucket name not available. Cannot save.")
        return False

    try:
        bucket = client.get_bucket(bucket_name)
        blob = bucket.blob(filename)
        
        csv_buffer = io.StringIO()
        dataframe.to_csv(csv_buffer, index=False)
        blob.upload_from_string(csv_buffer.getvalue(), content_type='text/csv')
        st.success("Image data saved persistently to GCS CSV!")
        return True
    except Exception as e:
        st.error(f"Error saving images to GCS CSV: {e}")
        return False

# --- App Title and Description ---
st.set_page_config(layout="centered")

st.title("Live Camera Image Storage (Permanent with GCS CSV)")
st.write("Capture photos from your webcam and store their Base64 data permanently in a CSV file on Google Cloud Storage.")

# --- User ID Display (Conceptual for multi-user) ---
# For a multi-user app, you would manage user authentication and assign unique IDs.
# For this demo, we'll use a fixed user ID.
if 'user_id' not in st.session_state:
    st.session_state.user_id = "demo_user_gcs"

st.markdown(f"Your User ID for Storage: `{st.session_state.user_id}`")
st.markdown("---")

# --- Load images at the start of the app ---
# This will load the CSV data from GCS into session state for display and modification
if 'current_images_df' not in st.session_state:
    st.session_state.current_images_df = load_images_from_gcs_csv(gcs_client, gcs_bucket_name, gcs_csv_filename)

# --- Camera Input Section ---
st.header("Capture a Photo")
captured_image_file = st.camera_input("Take a picture")

if captured_image_file:
    st.image(captured_image_file, caption="Captured Image Preview", use_column_width=True)

    if st.button("Save Image to GCS CSV"):
        if gcs_client and gcs_bucket_name:
            try:
                # Read image bytes
                image_bytes = captured_image_file.getvalue()

                # Convert to Base64 for storage in CSV
                base64_image = base64.b64encode(image_bytes).decode('utf-8')

                # Create a new row for the DataFrame
                new_image_entry = pd.DataFrame([{
                    'id': str(datetime.now().timestamp()), # Unique ID for this image
                    'timestamp': datetime.now().isoformat(),
                    'image_b64': base64_image
                }])

                # Append to the current DataFrame in session state
                st.session_state.current_images_df = pd.concat([st.session_state.current_images_df, new_image_entry], ignore_index=True)
                
                # Save the updated DataFrame back to GCS
                if save_images_to_gcs_csv(gcs_client, gcs_bucket_name, gcs_csv_filename, st.session_state.current_images_df):
                    st.experimental_rerun() # Rerun to display updated list from GCS
                
            except Exception as e:
                st.error(f"Error processing image for saving: {e}")
        else:
            st.warning("GCS client or bucket not available. Cannot save image.")

st.markdown("---")

# --- Display Saved Pictures from GCS CSV ---
st.header("My Saved Pictures (from GCS)")

if not st.session_state.current_images_df.empty:
    # Display images in reverse order (most recent first)
    images_to_display = st.session_state.current_images_df.to_dict(orient='records')

    for i, img_data in enumerate(reversed(images_to_display)):
        st.subheader(f"Picture taken on: {datetime.fromisoformat(img_data['timestamp']).strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Decode Base64 string back to bytes for st.image
        image_bytes = base64.b64decode(img_data['image_b64'])
        st.image(image_bytes, use_column_width=True)

        if st.button(f"Delete Picture {i+1}", key=f"delete_gcs_{img_data['id']}"):
            if gcs_client and gcs_bucket_name:
                try:
                    # Remove the row from the DataFrame
                    st.session_state.current_images_df = st.session_state.current_images_df[
                        st.session_state.current_images_df['id'] != img_data['id']
                    ].reset_index(drop=True)

                    # Save the updated DataFrame back to GCS
                    if save_images_to_gcs_csv(gcs_client, gcs_bucket_name, gcs_csv_filename, st.session_state.current_images_df):
                        st.experimental_rerun() # Rerun to update the display
                except Exception as e:
                    st.error(f"Error processing deletion: {e}")
            else:
                st.warning("GCS client or bucket not available. Cannot delete.")
        st.markdown("---")
else:
    st.info("No pictures found in GCS for this user. Take one!")

