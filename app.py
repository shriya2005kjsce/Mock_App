import React, { useState, useEffect, useRef } from 'react';
import { initializeApp } from 'firebase/app';
import { getAuth, signInAnonymously, signInWithCustomToken, onAuthStateChanged } from 'firebase/auth';
import { getFirestore, collection, addDoc, query, orderBy, onSnapshot, deleteDoc, doc, serverTimestamp } from 'firebase/firestore';

// Global variables provided by the Canvas environment
const appId = typeof __app_id !== 'undefined' ? __app_id : 'default-app-id';
const firebaseConfig = typeof __firebase_config !== 'undefined' ? JSON.parse(__firebase_config) : {};
const initialAuthToken = typeof __initial_auth_token !== 'undefined' ? __initial_auth_token : null;

function App() {
  const [db, setDb] = useState(null);
  const [auth, setAuth] = useState(null);
  const [userId, setUserId] = useState(null);
  const [isAuthReady, setIsAuthReady] = useState(false);
  const [capturedImageBlob, setCapturedImageBlob] = useState(null); // Stores the captured image as a Blob
  const [imagePreviewUrl, setImagePreviewUrl] = useState(null); // Stores URL for preview
  const [images, setImages] = useState([]); // Stores fetched images from Firestore
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState('');
  const [cameraActive, setCameraActive] = useState(false); // State to manage camera stream
  const videoRef = useRef(null); // Reference to the video element for live stream
  const canvasRef = useRef(null); // Reference to the canvas element for capturing photos

  // 1. Initialize Firebase and handle authentication
  useEffect(() => {
    try {
      const app = initializeApp(firebaseConfig);
      const authInstance = getAuth(app);
      const firestoreInstance = getFirestore(app);

      setAuth(authInstance);
      setDb(firestoreInstance);

      // Listen for authentication state changes
      const unsubscribe = onAuthStateChanged(authInstance, async (user) => {
        if (user) {
          setUserId(user.uid);
          setIsAuthReady(true);
        } else {
          // If no user, try to sign in with custom token or anonymously
          try {
            if (initialAuthToken) {
              await signInWithCustomToken(authInstance, initialAuthToken);
            } else {
              await signInAnonymously(authInstance);
            }
          } catch (error) {
            console.error("Firebase authentication error:", error);
            setMessage(`Authentication failed: ${error.message}`);
          }
        }
      });

      return () => unsubscribe(); // Cleanup auth listener on component unmount
    } catch (error) {
      console.error("Firebase initialization error:", error);
      setMessage(`Firebase initialization failed: ${error.message}`);
    }
  }, []);

  // 2. Fetch images from Firestore once authenticated
  useEffect(() => {
    if (isAuthReady && db && userId) {
      const imagesCollectionRef = collection(db, `artifacts/${appId}/users/${userId}/camera_images`);
      // Order by timestamp to show most recent first
      const q = query(imagesCollectionRef, orderBy('timestamp', 'desc'));

      const unsubscribe = onSnapshot(q, (snapshot) => {
        const fetchedImages = snapshot.docs.map(doc => ({
          id: doc.id,
          ...doc.data()
        }));
        setImages(fetchedImages);
        setMessage(''); // Clear any previous messages
      }, (error) => {
        console.error("Error fetching images:", error);
        setMessage(`Error fetching images: ${error.message}`);
      });

      return () => unsubscribe(); // Cleanup snapshot listener
    }
  }, [isAuthReady, db, userId]);

  // Function to start camera stream
  const startCamera = async () => {
    setLoading(true);
    setMessage('Starting camera...');
    try {
      
      const stream = await navigator.mediaDevices.getUserMedia({ video: true });
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        videoRef.current.play();
        setCameraActive(true);
        setMessage('Camera active.');
      }
    } catch (err) {
      console.error("Error accessing camera:", err);
      setMessage(`Error accessing camera: ${err.message}. Please allow camera access.`);
      setCameraActive(false);
    } finally {
      setLoading(false);
    }
  };

  // Function to stop camera stream
  const stopCamera = () => {
    if (videoRef.current && videoRef.current.srcObject) {
      videoRef.current.srcObject.getTracks().forEach(track => track.stop());
      videoRef.current.srcObject = null;
    }
    setCameraActive(false);
    setCapturedImageBlob(null);
    setImagePreviewUrl(null);
    setMessage('');
  };

  // Capture photo from video stream
  const capturePhoto = () => {
    if (videoRef.current && canvasRef.current) {
      const video = videoRef.current;
      const canvas = canvasRef.current;

      // Set canvas dimensions to match video
      canvas.width = video.videoWidth;
      canvas.height = video.videoHeight;

      const context = canvas.getContext('2d');
      context.drawImage(video, 0, 0, canvas.width, canvas.height);

      // Get image data from canvas as Blob
      canvas.toBlob((blob) => {
        if (blob) {
          setCapturedImageBlob(blob);
          setImagePreviewUrl(URL.createObjectURL(blob));
          setMessage('Photo captured!');
        } else {
          setMessage('Failed to capture photo.');
        }
      }, 'image/jpeg', 0.9); // Save as JPEG with 90% quality
    }
  };

  // Save the captured image Blob to Firestore
  const saveImageToFirestore = async () => {
    if (!capturedImageBlob) {
      setMessage('Please capture a photo first.');
      return;
    }
    if (!db || !userId) {
      setMessage('Database not ready. Please wait or refresh.');
      return;
    }

    setLoading(true);
    setMessage('Saving image...');

    try {
      const reader = new FileReader();
      reader.readAsDataURL(capturedImageBlob); // Reads as Base64 string
      reader.onloadend = async () => {
        const base64Image = reader.result; // "data:image/jpeg;base64,..."

        const imagesCollectionRef = collection(db, `artifacts/${appId}/users/${userId}/camera_images`);
        await addDoc(imagesCollectionRef, {
          image_b64: base64Image,
          timestamp: serverTimestamp(), // Use server timestamp for consistency
          userId: userId,
        });

        setMessage('Image saved successfully!');
        setCapturedImageBlob(null); // Clear captured image after saving
        setImagePreviewUrl(null);
        stopCamera(); // Stop camera after saving
      };
      reader.onerror = (error) => {
        console.error("Error reading image file:", error);
        setMessage(`Error reading image: ${error.message}`);
        setLoading(false);
      };

    } catch (error) {
      console.error("Error saving image to Firestore:", error);
      setMessage(`Error saving image: ${error.message}`);
    } finally {
      setLoading(false);
    }
  };

  // Delete an image from Firestore
  const deleteImageFromFirestore = async (imageId) => {
    if (!db || !userId) {
      setMessage('Database not ready. Cannot delete.');
      return;
    }

    setLoading(true);
    setMessage('Deleting image...');

    try {
      const imageDocRef = doc(db, `artifacts/${appId}/users/${userId}/camera_images`, imageId);
      await deleteDoc(imageDocRef);
      setMessage('Image deleted successfully!');
    } catch (error) {
      console.error("Error deleting image from Firestore:", error);
      setMessage(`Error deleting image: ${error.message}`);
    } finally {
      setLoading(false);
    }
  };

  // Stop camera when component unmounts or user navigates away
  useEffect(() => {
    return () => {
      stopCamera();
    };
  }, []);

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-100 to-purple-200 p-4 sm:p-6 font-sans flex flex-col items-center">
      <div className="bg-white rounded-xl shadow-lg p-6 sm:p-8 w-full max-w-2xl">
        <h1 className="text-3xl sm:text-4xl font-bold text-center text-gray-800 mb-6">
          📸 Live Camera Image Storage
        </h1>
        <p className="text-center text-gray-600 mb-6">
          Capture and store your moments securely in the cloud!
        </p>

        {userId && (
          <p className="text-sm text-gray-500 text-center mb-4">
            Your User ID: <span className="font-mono break-all">{userId}</span>
          </p>
        )}

        <div className="flex flex-col items-center space-y-4 mb-8">
          {!cameraActive ? (
            <button
              onClick={startCamera}
              disabled={loading}
              className={`w-full sm:w-auto px-8 py-3 rounded-lg font-semibold transition duration-300 ease-in-out
                ${loading
                  ? 'bg-gray-300 text-gray-600 cursor-not-allowed'
                  : 'bg-blue-500 hover:bg-blue-600 text-white shadow-md transform hover:scale-105'
                }`}
            >
              {loading ? 'Starting Camera...' : 'Start Camera'}
            </button>
          ) : (
            <>
              <video ref={videoRef} className="w-full max-w-md rounded-lg shadow-md border-2 border-gray-300" autoPlay playsInline muted></video>
              <canvas ref={canvasRef} className="hidden"></canvas> {/* Hidden canvas for capturing */}
              <div className="flex space-x-4">
                <button
                  onClick={capturePhoto}
                  disabled={loading}
                  className={`px-8 py-3 rounded-lg font-semibold transition duration-300 ease-in-out
                    ${loading
                      ? 'bg-gray-300 text-gray-600 cursor-not-allowed'
                      : 'bg-indigo-500 hover:bg-indigo-600 text-white shadow-md transform hover:scale-105'
                    }`}
                >
                  Capture Photo
                </button>
                <button
                  onClick={stopCamera}
                  disabled={loading}
                  className={`px-8 py-3 rounded-lg font-semibold transition duration-300 ease-in-out
                    ${loading
                      ? 'bg-gray-300 text-gray-600 cursor-not-allowed'
                      : 'bg-red-500 hover:bg-red-600 text-white shadow-md transform hover:scale-105'
                    }`}
                >
                  Stop Camera
                </button>
              </div>
            </>
          )}

          {imagePreviewUrl && (
            <div className="mt-4 border-2 border-gray-300 rounded-lg overflow-hidden shadow-md">
              <img
                src={imagePreviewUrl}
                alt="Captured Preview"
                className="max-w-full h-auto rounded-md"
                style={{ maxHeight: '300px' }}
              />
            </div>
          )}

          <button
            onClick={saveImageToFirestore}
            disabled={!capturedImageBlob || loading || !isAuthReady}
            className={`w-full sm:w-auto px-8 py-3 rounded-lg font-semibold transition duration-300 ease-in-out
              ${!capturedImageBlob || loading || !isAuthReady
                ? 'bg-gray-300 text-gray-600 cursor-not-allowed'
                : 'bg-green-500 hover:bg-green-600 text-white shadow-md transform hover:scale-105'
              }`}
          >
            {loading ? 'Saving...' : 'Save Image to Cloud'}
          </button>
        </div>

        {message && (
          <p className={`text-center text-sm ${message.includes('Error') ? 'text-red-500' : 'text-green-600'} mt-4`}>
            {message}
          </p>
        )}

        <hr className="my-8 border-t-2 border-gray-200" />

        <h2 className="text-2xl sm:text-3xl font-bold text-center text-gray-800 mb-6">
          My Saved Pictures
        </h2>

        {loading && images.length === 0 && (
          <p className="text-center text-gray-500">Loading images...</p>
        )}

        {images.length === 0 && !loading && (
          <p className="text-center text-gray-500">No images saved yet. Take one!</p>
        )}

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
          {images.map((img) => (
            <div key={img.id} className="bg-gray-50 rounded-lg shadow-md overflow-hidden flex flex-col">
              <img
                src={img.image_b64}
                alt={`Saved ${img.id}`}
                className="w-full h-48 object-cover rounded-t-lg"
                onError={(e) => { e.target.onerror = null; e.target.src = "https://placehold.co/400x300/CCCCCC/000000?text=Image+Error"; }}
              />
              <div className="p-4 flex-grow flex flex-col justify-between">
                <div>
                  <p className="text-sm text-gray-600 mb-2">
                    {img.timestamp ? new Date(img.timestamp.toDate()).toLocaleString() : 'Saving...'}
                  </p>
                </div>
                <button
                  onClick={() => deleteImageFromFirestore(img.id)}
                  disabled={loading}
                  className={`mt-3 w-full py-2 px-4 rounded-md font-semibold transition duration-300 ease-in-out
                    ${loading
                      ? 'bg-red-300 text-gray-600 cursor-not-allowed'
                      : 'bg-red-500 hover:bg-red-600 text-white shadow-sm transform hover:scale-105'
                    }`}
                >
                  Delete
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

export default App;
