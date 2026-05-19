from unittest.mock import Mock, patch

import httpx

from app.core.config import Settings
from models.integrity_proof import (
    anchor_ipfs_hash,
    canonicalize_report,
    create_integrity_proof,
    pin_report_to_ipfs,
)


def test_canonicalize_report_is_stable() -> None:
    """
    Verifies that report payloads serialize deterministically before hashing.
    """
    first = canonicalize_report({"b": 2, "a": 1})
    second = canonicalize_report({"a": 1, "b": 2})

    assert first == second
    assert first == '{"a":1,"b":2}'


def test_pin_report_to_ipfs_parses_pinning_response() -> None:
    """
    Verifies IPFS pinning without making a live API call.
    """
    settings = Settings(
        ipfs_api_url="https://pinning.example.com/pin",
        ipfs_api_key="test-key",
    )
    response = httpx.Response(
        status_code=200,
        request=httpx.Request("POST", settings.ipfs_api_url),
        json={"IpfsHash": "QmTestCid"},
    )

    with patch("models.integrity_proof.httpx.post", return_value=response) as mock_post:
        cid = pin_report_to_ipfs({"id": "report-1"}, settings)

    assert cid == "QmTestCid"
    assert mock_post.call_args.kwargs["headers"]["Authorization"] == "Bearer test-key"


def test_anchor_ipfs_hash_uses_web3_transaction() -> None:
    """
    Verifies blockchain anchoring without submitting a real transaction.
    """
    settings = Settings(
        web3_provider_url="https://rpc.example.com",
        web3_private_key="0xabc",
        web3_chain_id=11155111,
        proof_contract_address="0x000000000000000000000000000000000000dEaD",
    )
    fake_account = Mock()
    fake_account.address = "0x000000000000000000000000000000000000bEEF"
    fake_signed = Mock()
    fake_signed.raw_transaction = b"signed"

    fake_web3 = Mock()
    fake_web3.eth.account.from_key.return_value = fake_account
    fake_web3.eth.account.sign_transaction.return_value = fake_signed
    fake_web3.eth.get_transaction_count.return_value = 7
    fake_web3.eth.gas_price = 100
    fake_web3.eth.send_raw_transaction.return_value = bytes.fromhex("12" * 32)
    fake_web3.eth.wait_for_transaction_receipt.return_value = Mock(blockNumber=123)
    fake_web3.to_hex.return_value = "0x" + "12" * 32
    fake_web3.to_checksum_address.side_effect = lambda value: value

    with patch("models.integrity_proof._build_web3", return_value=fake_web3):
        proof = anchor_ipfs_hash("QmTestCid", "0x" + "34" * 32, settings)

    assert proof.transaction_hash == "0x" + "12" * 32
    assert proof.block_number == 123
    assert proof.ipfs_hash == "QmTestCid"
    assert proof.network == "EVM Testnet"


def test_create_integrity_proof_falls_back_without_credentials() -> None:
    """
    Verifies local proof fallback when IPFS or blockchain is not configured.
    """
    proof = create_integrity_proof(
        report_id="report-1",
        report_payload={"id": "report-1"},
        settings=Settings(),
    )

    assert proof.transaction_hash.startswith("0x")
    assert proof.block_number == 0
    assert proof.ipfs_hash.startswith("local-")
    assert proof.network == "Local Integrity Proof"
