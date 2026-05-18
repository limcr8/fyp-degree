
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

export interface VerificationResult {
  id: string;
  text: string;
  status: VerificationStatus;
  confidence: number;
  explanation: string;
  shapData: ShapExplanation[];
  sources: SourceMatch[];
  blockchain: BlockchainProof;
}

export type ViewType = 'verify' | 'admin' | 'history' | 'login' | 'signup';
