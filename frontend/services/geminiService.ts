
import { GoogleGenAI, Type } from "@google/genai";
import { VerificationStatus, VerificationResult } from "../types";

const ai = new GoogleGenAI({ apiKey: process.env.API_KEY || '' });

export const verifyNewsContent = async (text: string): Promise<Partial<VerificationResult>> => {
  const prompt = `Analyze the following news text for authenticity. 
  Provide a truthfulness score, a detailed explanation, and identify specific keywords that contributed to the verdict (mimicking SHAP values).
  
  News Text: "${text}"`;

  try {
    const response = await ai.models.generateContent({
      model: "gemini-3-flash-preview",
      contents: prompt,
      config: {
        responseMimeType: "application/json",
        responseSchema: {
          type: Type.OBJECT,
          properties: {
            status: { type: Type.STRING, description: "REAL, FAKE, or UNCERTAIN" },
            confidence: { type: Type.NUMBER },
            explanation: { type: Type.STRING },
            shapData: {
              type: Type.ARRAY,
              items: {
                type: Type.OBJECT,
                properties: {
                  word: { type: Type.STRING },
                  weight: { type: Type.NUMBER }
                }
              }
            }
          },
          required: ["status", "confidence", "explanation", "shapData"]
        }
      }
    });

    const data = JSON.parse(response.text);
    return data;
  } catch (error) {
    console.error("Gemini Error:", error);
    throw error;
  }
};

export const searchGrounding = async (text: string) => {
  const response = await ai.models.generateContent({
    model: "gemini-3-flash-preview",
    contents: `Fact check this news snippet: "${text}". List URLs of news articles that confirm or debunk this.`,
    config: {
      tools: [{ googleSearch: {} }]
    }
  });

  return {
    text: response.text,
    sources: response.candidates?.[0]?.groundingMetadata?.groundingChunks || []
  };
};
