const firebaseConfig = {
  apiKey: "AIzaSyALY7CGLl174-Fk7LGK4DvGeOu-FktIeE",
  authDomain: "app-forge-f7a07.firebaseapp.com",
  projectId: "app-forge-f7a07",
  storageBucket: "app-forge-f7a07.firebasestorage.app",
  messagingSenderId: "579204050538",
  appId: "1:579204050538:web:5e52487a75730d958e2413"
};

const app = firebase.initializeApp(firebaseConfig);
const auth = firebase.auth();
const db = firebase.firestore();
