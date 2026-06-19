import json
import logging
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any

import httpx

from app.core.config import Settings, get_settings
from app.schemas.analysis import BlockchainProof

logger = logging.getLogger(__name__)


def create_integrity_proof(
    report_id: str,
    report_payload: dict[str, Any],
    settings: Settings | None = None,
) -> BlockchainProof:
    """
    Pins a report to IPFS and anchors its CID/hash on an EVM testnet.

    Args:
        report_id (str): Stable report identifier.
        report_payload (dict[str, Any]): Report content before blockchain proof.
        settings (Settings | None): Optional runtime settings override.

    Returns:
        BlockchainProof: Integrity proof metadata.
    """
    active_settings = settings or get_settings()
    report_hash = hash_report(report_payload)

    if not _ipfs_is_configured(active_settings) or not _web3_is_configured(active_settings):
        return build_local_proof(report_id, report_hash)

    try:
        ipfs_hash = pin_report_to_ipfs(report_payload, active_settings)
        return anchor_ipfs_hash(report_id, ipfs_hash, report_hash, active_settings)
    except Exception:
        logger.exception("Integrity proof creation failed.")
        return build_local_proof(report_id, report_hash)


def canonicalize_report(report_payload: dict[str, Any]) -> str:
    """
    Serializes a report deterministically for hashing and IPFS pinning.

    Args:
        report_payload (dict[str, Any]): Report content.

    Returns:
        str: Canonical JSON string.
    """
    return json.dumps(
        report_payload,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )


def hash_report(report_payload: dict[str, Any]) -> str:
    """
    Hashes a canonical report payload.

    Args:
        report_payload (dict[str, Any]): Report content.

    Returns:
        str: Hex-encoded SHA-256 digest with 0x prefix.
    """
    canonical_report = canonicalize_report(report_payload)
    digest = sha256(canonical_report.encode("utf-8")).hexdigest()
    return f"0x{digest}"


def pin_report_to_ipfs(report_payload: dict[str, Any], settings: Settings) -> str:
    """
    Pins the canonical report payload to an IPFS-compatible pinning API.

    Args:
        report_payload (dict[str, Any]): Report content.
        settings (Settings): Runtime settings with IPFS credentials.

    Returns:
        str: IPFS content identifier.
    """
    response = httpx.post(
        settings.ipfs_api_url,
        headers={
            "Authorization": f"Bearer {settings.ipfs_api_key}",
            "Content-Type": "application/json",
        },
        json={
            "pinataContent": report_payload,
            "pinataMetadata": {"name": f"fake-news-report-{report_payload['id']}"},
        },
        timeout=5,
    )
    response.raise_for_status()
    payload = response.json()
    ipfs_hash = payload.get("IpfsHash") or payload.get("Hash") or payload.get("cid")

    if not ipfs_hash:
        raise ValueError("IPFS pinning response did not include a content hash.")

    return str(ipfs_hash)


def anchor_ipfs_hash(
    report_id: str,
    ipfs_hash: str,
    report_hash: str,
    settings: Settings,
) -> BlockchainProof:
    """
    Anchors an IPFS CID and report hash on an EVM-compatible testnet.

    Args:
        report_id (str): Unique report identifier.
        ipfs_hash (str): IPFS content identifier.
        report_hash (str): Report SHA-256 digest.
        settings (Settings): Runtime settings with Web3 credentials.

    Returns:
        BlockchainProof: Blockchain transaction metadata.
    """
    web3 = _build_web3(settings.web3_provider_url)
    account = web3.eth.account.from_key(settings.web3_private_key)

    if settings.proof_contract_address:
        # Use Smart Contract anchorReport function
        contract_abi = [
            {
                "inputs": [
                    {"internalType": "string", "name": "_reportId", "type": "string"},
                    {"internalType": "string", "name": "_ipfsHash", "type": "string"},
                    {"internalType": "bytes32", "name": "_reportHash", "type": "bytes32"}
                ],
                "name": "anchorReport",
                "outputs": [],
                "stateMutability": "nonpayable",
                "type": "function"
            }
        ]
        contract_address = web3.to_checksum_address(settings.proof_contract_address)
        contract = web3.eth.contract(address=contract_address, abi=contract_abi)
        
        # Clean hex and convert report hash to bytes32 representation
        clean_hash = report_hash.replace("0x", "")
        report_hash_bytes = bytes.fromhex(clean_hash.ljust(64, "0")[:64])

        tx_build = contract.functions.anchorReport(
            report_id,
            ipfs_hash,
            report_hash_bytes
        ).build_transaction({
            "from": account.address,
            "nonce": web3.eth.get_transaction_count(account.address),
            "gas": 150000,
            "gasPrice": web3.eth.gas_price,
            "chainId": settings.web3_chain_id,
        })
    else:
        # Fallback to raw data memo transfer
        destination = account.address
        data = _encode_anchor_data(ipfs_hash, report_hash)
        tx_build = {
            "to": web3.to_checksum_address(destination),
            "value": 0,
            "data": data,
            "nonce": web3.eth.get_transaction_count(account.address),
            "gas": 100000,
            "gasPrice": web3.eth.gas_price,
            "chainId": settings.web3_chain_id,
        }

    signed_transaction = web3.eth.account.sign_transaction(
        tx_build,
        settings.web3_private_key,
    )
    transaction_hash = web3.eth.send_raw_transaction(
        signed_transaction.raw_transaction
    )
    receipt = web3.eth.wait_for_transaction_receipt(transaction_hash)

    return BlockchainProof(
        transactionHash=web3.to_hex(transaction_hash),
        blockNumber=receipt.blockNumber,
        timestamp=_utc_timestamp(),
        ipfsHash=ipfs_hash,
        network="EVM Testnet",
    )


def build_local_proof(report_id: str, report_hash: str) -> BlockchainProof:
    """
    Builds deterministic local proof metadata when external proofing is disabled.

    Args:
        report_id (str): Stable report identifier.
        report_hash (str): Report SHA-256 digest.

    Returns:
        BlockchainProof: Local proof metadata.
    """
    digest = sha256(f"{report_id}:{report_hash}".encode("utf-8")).hexdigest()
    return BlockchainProof(
        transactionHash=f"0x{digest}",
        blockNumber=0,
        timestamp=_utc_timestamp(),
        ipfsHash=f"local-{digest[:46]}",
        network="Local Integrity Proof",
    )


def _encode_anchor_data(ipfs_hash: str, report_hash: str) -> str:
    """
    Encodes proof data as UTF-8 hex for a simple EVM transaction memo.

    Args:
        ipfs_hash (str): IPFS content identifier.
        report_hash (str): Report SHA-256 digest.

    Returns:
        str: Hex-encoded transaction data.
    """
    proof_text = canonicalize_report({"ipfsHash": ipfs_hash, "reportHash": report_hash})
    return f"0x{proof_text.encode('utf-8').hex()}"


def _build_web3(provider_url: str) -> Any:
    """
    Builds a Web3 client lazily.

    Args:
        provider_url (str): EVM RPC provider URL.

    Returns:
        Any: Web3 client.
    """
    try:
        from web3 import Web3
    except ImportError as exc:
        raise RuntimeError("web3.py is required for blockchain anchoring.") from exc

    return Web3(Web3.HTTPProvider(provider_url))


def _ipfs_is_configured(settings: Settings) -> bool:
    """
    Checks whether IPFS pinning credentials are configured.

    Args:
        settings (Settings): Runtime settings.

    Returns:
        bool: Whether IPFS pinning is configured.
    """
    return bool(settings.ipfs_api_url and settings.ipfs_api_key)


def _web3_is_configured(settings: Settings) -> bool:
    """
    Checks whether EVM anchoring credentials are configured.

    Args:
        settings (Settings): Runtime settings.

    Returns:
        bool: Whether EVM anchoring is configured.
    """
    return bool(
        settings.web3_provider_url
        and settings.web3_private_key
        and settings.web3_chain_id
    )


def _utc_timestamp() -> str:
    """
    Returns a frontend-compatible UTC timestamp.

    Returns:
        str: Timestamp string.
    """
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
