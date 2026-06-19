
export enum VerificationStatus {
  REAL = 'REAL',
  FAKE = 'FAKE',
  UNCERTAIN = 'UNCERTAIN'
}

export interface ShapExplanation {
  word: string;
  weight: number;
}

export interface SourceMatch {
  name: string;
  confirmed: boolean;
  url?: string;
}

export interface BlockchainProof {
  transactionHash: string;
  blockNumber: number;
  timestamp: string;
  ipfsHash: string;
  network: string;
}

export interface ClassificationDetail {
  verdict: string;
  confidence: number;
  riskLevel: string;
  explanation: string;
}

export interface ExplanationDetail {
  shapData: ShapExplanation[];
  summary: string;
  topFactors: string[];
}

export interface SourceComparison {
  source_name: string;
  article_title: string;
  relationship: 'SUPPORTS' | 'REFUTES' | 'UNRELATED';
  key_finding: string;
}

export interface MatchingArticle {
  title: string;
  link: string;
  source: string;
  snippet: string;
}

export interface VerificationDetail {
  sources: SourceMatch[];
  verificationScore: number;
  explanation: string;
  matchingArticles?: MatchingArticle[];
  summary?: string;
  sourceComparison?: SourceComparison[];
}

export interface FinalAssessment {
  score: number;
  label: string;
  reasoning: string;
}

export interface VerificationResult {
  id: string;
  text: string;
  classification: ClassificationDetail;
  explanation: ExplanationDetail;
  verification: VerificationDetail;
  finalAssessment: FinalAssessment;
  blockchain: BlockchainProof;
  processingTimeMs: number;
  status?: string; // Optional support for backward compatibility
  confidence?: number;
  explanationStr?: string; // Mapped dynamically
  sourcesList?: SourceMatch[];
  createdAt?: string;
  platform?: string;
  language?: string;
}

export type ViewType = 'verify' | 'admin' | 'history' | 'login' | 'signup' | 'portal' | 'profile';
