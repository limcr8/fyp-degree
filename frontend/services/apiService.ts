import { VerificationResult } from "../types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export const verifyNewsContent = async (text: string): Promise<VerificationResult> => {
  const response = await fetch(`${API_BASE_URL}/analyze`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ text }),
  });

  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || "Verification request failed.");
  }

  return response.json() as Promise<VerificationResult>;
};
