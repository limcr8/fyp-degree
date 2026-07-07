import { initializeApp, getApps, getApp } from "firebase/app";
import { 
  getAuth, 
  GoogleAuthProvider, 
  signInWithPopup, 
  signOut
} from "firebase/auth";
import { 
  getFirestore, 
  doc, 
  setDoc, 
  updateDoc, 
  getDocs, 
  collection, 
  query, 
  orderBy 
} from "firebase/firestore";
import { VerificationResult } from "../types";

const firebaseConfig = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY,
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID,
  storageBucket: import.meta.env.VITE_FIREBASE_STORAGE_BUCKET,
  messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID,
  appId: import.meta.env.VITE_FIREBASE_APP_ID,
};

// Initialize Firebase (safeguard against multiple initializations during hot reloads)
const app = getApps().length === 0 ? initializeApp(firebaseConfig) : getApp();

export const auth = getAuth(app);
export const db = getFirestore(app);

// Computes the Firestore user document ID from an email address.
// MUST mirror the backend: hashlib.sha256(email.strip().lower()).hexdigest()
// (see backend/models/auth_service.py). The backend creates each user document
// at users/{email_hash}; if the frontend used the Firebase Auth UID instead,
// Firestore would implicitly create a duplicate users/{uid} document whenever
// a history subcollection is written.
const _userDocIdFromEmail = async (email: string): Promise<string> => {
  const normalized = (email || "").trim().toLowerCase();
  const data = new TextEncoder().encode(normalized);
  const digestBuffer = await crypto.subtle.digest("SHA-256", data);
  return Array.from(new Uint8Array(digestBuffer))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
};

// Google Auth Provider
const googleProvider = new GoogleAuthProvider();

export const signInWithGoogle = async () => {
  try {
    const result = await signInWithPopup(auth, googleProvider);
    return result.user;
  } catch (error) {
    console.error("Google Sign-In Error:", error);
    throw error;
  }
};

export const logoutUser = async () => {
  try {
    await signOut(auth);
  } catch (error) {
    console.error("Sign-Out Error:", error);
    throw error;
  }
};

// Firestore helper: Save a verification result to the user's history subcollection
// NOTE: `userEmail` is resolved to the users/{sha256(email)} document so history
// is stored under the SAME user document the backend created at signup.
export const saveVerificationResult = async (userEmail: string, result: VerificationResult) => {
  try {
    const userId = await _userDocIdFromEmail(userEmail);
    const docId = result.id || (result as any).article_id || (result as any).id;
    if (!docId) {
      throw new Error("Cannot save verification result: missing unique identifier.");
    }

    // Resolve the authoritative verdict the same way the UI displays it:
    // finalAssessment.label takes priority, falling back to classification.verdict.
    // This guarantees Firestore stores the same verdict the user sees, avoiding
    // the previous mismatch where articles showed FAKE but history kept UNCERTAIN.
    const resolvedVerdict = (
      result.finalAssessment?.label ||
      (result as any).final_assessment?.label ||
      result.classification?.verdict ||
      'UNCERTAIN'
    ).toString().toUpperCase().replace(/_/g, ' ');

    const cleanResult = {
      id: docId,
      text: result.text,
      classification: result.classification ? {
        verdict: resolvedVerdict,
        confidence: result.classification.confidence,
        riskLevel: result.classification.riskLevel || (result.classification as any).risk_level,
        explanation: result.classification.explanation
      } : {
        verdict: resolvedVerdict,
        confidence: result.finalAssessment?.score ?? 0,
        riskLevel: 'medium',
        explanation: ''
      },
      explanation: result.explanation ? {
        shapData: result.explanation.shapData || (result.explanation as any).shap_data || [],
        summary: result.explanation.summary,
        topFactors: result.explanation.topFactors || (result.explanation as any).top_factors || [],
        factualSignal: (result.explanation as any).factualSignal || (result.explanation as any).factual_signal || "Medium",
        biasSignal: (result.explanation as any).biasSignal || (result.explanation as any).bias_signal || "Low"
      } : null,
      verification: result.verification ? {
        sources: result.verification.sources || (result.verification as any).sources || [],
        verificationScore: result.verification.verificationScore !== undefined 
          ? result.verification.verificationScore 
          : (result.verification as any).verification_score,
        explanation: result.verification.explanation,
        matchingArticles: result.verification.matchingArticles || (result.verification as any).matching_articles || [],
        summary: result.verification.summary || "",
        sourceComparison: result.verification.sourceComparison || (result.verification as any).source_comparison || []
      } : null,
      finalAssessment: result.finalAssessment ? {
        score: result.finalAssessment.score,
        label: result.finalAssessment.label,
        reasoning: result.finalAssessment.reasoning
      } : (result as any).final_assessment ? {
        score: (result as any).final_assessment.score,
        label: (result as any).final_assessment.label,
        reasoning: (result as any).final_assessment.reasoning
      } : {
        score: 0,
        label: resolvedVerdict.toLowerCase(),
        reasoning: ''
      },
      blockchain: result.blockchain ? {
        transactionHash: result.blockchain.transactionHash || (result.blockchain as any).transaction_hash,
        blockNumber: result.blockchain.blockNumber || (result.blockchain as any).block_number,
        timestamp: result.blockchain.timestamp,
        ipfsHash: result.blockchain.ipfsHash || (result.blockchain as any).ipfs_hash,
        network: result.blockchain.network
      } : (result as any).blockchain ? {
        transactionHash: (result as any).blockchain.transaction_hash || (result as any).blockchain.transactionHash,
        blockNumber: (result as any).blockchain.block_number || (result as any).blockchain.blockNumber,
        timestamp: (result as any).blockchain.timestamp,
        ipfsHash: (result as any).blockchain.ipfs_hash || (result as any).blockchain.ipfsHash,
        network: (result as any).blockchain.network
      } : null,
      processingTimeMs: result.processingTimeMs !== undefined ? result.processingTimeMs : (result as any).processing_time_ms || 0,
      platform: result.platform || "website",
      language: result.language || "en",
      createdAt: result.createdAt || (result as any).created_at || new Date().toISOString()
    };

    const sanitized = JSON.parse(JSON.stringify(cleanResult));
    const timestamp = new Date().toISOString();

    // 1. Save to user's history subcollection. Uses the same `sanitized`
    // payload as the articles write below so the verdict (and every other
    // field) is identical across both collections.
    const userDocRef = doc(db, "users", userId, "history", docId);
    const userPayload = JSON.parse(JSON.stringify({
      ...sanitized,
      timestamp,
    }));
    await setDoc(userDocRef, userPayload);

    // 2. Save to global articles collection for the Public Portal
    const articleDocRef = doc(db, "articles", docId);
    const articlePayload = JSON.parse(JSON.stringify({
      ...sanitized,
      article_id: docId,
      verified_at: sanitized.createdAt || timestamp,
      timestamp,
    }));
    await setDoc(articleDocRef, articlePayload);
  } catch (error) {
    console.error("Error saving verification result:", error);
    throw error;
  }
};

// Firestore helper: Retrieve the user's verification history
// NOTE: `userEmail` is resolved to the users/{sha256(email)} document so we read
// from the SAME user document the backend created at signup.
export const getVerificationHistory = async (userEmail: string): Promise<VerificationResult[]> => {
  try {
    const userId = await _userDocIdFromEmail(userEmail);
    const historyRef = collection(db, "users", userId, "history");
    const q = query(historyRef, orderBy("timestamp", "desc"));
    const querySnapshot = await getDocs(q);
    
    const results: VerificationResult[] = [];
    querySnapshot.forEach((docSnap) => {
      // Cast the document data to VerificationResult
      const data = docSnap.data();
      results.push(data as VerificationResult);
    });
    return results;
  } catch (error) {
    console.error("Error retrieving verification history:", error);
    throw error;
  }
};

// Firestore helper: Update the user's profile document in the 'users' collection
// NOTE: `userEmail` is resolved to the users/{sha256(email)} document so profile
// edits target the SAME user document the backend created at signup.
// The signup flow stores the display name in a field called 'name'
// (see SignupView.tsx), so we must update 'name' here — not 'username'.
export const updateUserProfileFirestore = async (
  userEmail: string,
  data: { name?: string; email?: string }
): Promise<void> => {
  try {
    const userId = await _userDocIdFromEmail(userEmail);
    const userDocRef = doc(db, "users", userId);
    await updateDoc(userDocRef, {
      ...(data.name !== undefined && { name: data.name }),
      ...(data.email !== undefined && { email: data.email }),
      updated_at: new Date().toISOString(),
    });
  } catch (error) {
    console.error("Error updating user profile in Firestore:", error);
    throw error;
  }
};

// Firestore helper: Save user feedback/dispute to the 'feedback' collection
export interface FeedbackRecord {
  article_id: string;
  feedback_type: string;
  message: string;
  user_email: string;
  verdict?: string;
  user_id?: string;
}

export const saveFeedback = async (record: FeedbackRecord): Promise<{ feedback_id: string }> => {
  try {
    const timestamp = new Date().toISOString();
    // Generate a unique feedback id
    const feedbackId = `feedback_${Date.now().toString(36)}${Math.random().toString(36).slice(2, 8)}`;

    const payload = {
      feedback_id: feedbackId,
      article_id: record.article_id,
      feedback_type: record.feedback_type,
      message: record.message,
      user_email: record.user_email,
      verdict: record.verdict || null,
      user_id: record.user_id || null,
      status: "open",
      created_at: timestamp,
    };

    // Save to the global 'feedback' collection in Firestore
    const docRef = doc(db, "feedback", feedbackId);
    await setDoc(docRef, payload);

    return { feedback_id: feedbackId };
  } catch (error) {
    console.error("Error saving feedback to Firebase:", error);
    throw error;
  }
};
