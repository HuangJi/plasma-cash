import pytest
import rlp
from ethereum import utils as eth_utils
from mockito import any, mock, verify, when

from plasma_cash.child_chain.block import Block
from plasma_cash.child_chain.child_chain import ChildChain
from plasma_cash.child_chain.exceptions import (InvalidBlockSignatureException,
                                                InvalidTxSignatureException,
                                                PreviousTxNotFoundException,
                                                TxAlreadySpentException,
                                                TxAmountMismatchException)
from plasma_cash.child_chain.transaction import Transaction
from unit_tests.unstub_mixin import UnstubMixin


class TestChildChain(UnstubMixin):
    DUMMY_AUTHORITY = b"\x14\x7f\x08\x1b\x1a6\xa8\r\xf0Y\x15(ND'\xc1\xf6\xdd\x98\x84"
    DUMMY_SIG = '01' * 65  # sig for DUMMY_AUTHORITY
    DUMMY_TX_NEW_OWNER = b'\xfd\x02\xec\xeeby~u\xd8k\xcf\xf1d.\xb0\x84J\xfb(\xc7'
    ROOT_CHAIN = mock()

    @pytest.fixture(scope='function')
    def child_chain(self):
        DUMMY_TX_OWNER = b'\x8cT\xa4\xa0\x17\x9f$\x80\x1fI\xf92-\xab<\x87\xeb\x19L\x9b'

        deposit_filter = mock()
        when(self.ROOT_CHAIN).on('Deposit').thenReturn(deposit_filter)
        child_chain = ChildChain(authority=self.DUMMY_AUTHORITY,
                                 root_chain=self.ROOT_CHAIN)

        # create a dummy transaction
        tx = Transaction(prev_block=0, uid=1, amount=10, new_owner=DUMMY_TX_OWNER)

        # create a block with the dummy transaction
        child_chain.blocks[1] = Block([tx])
        child_chain.current_block_number = 2
        return child_chain

    def test_constructor(self):
        deposit_filter = mock()
        when(self.ROOT_CHAIN).on('Deposit').thenReturn(deposit_filter)

        ChildChain(authority=self.DUMMY_AUTHORITY, root_chain=self.ROOT_CHAIN)

        verify(self.ROOT_CHAIN).on('Deposit')
        verify(deposit_filter).watch(any)

    def test_apply_deposit(self, child_chain):
        DUMMY_AMOUNT = 123
        DUMMY_UID = 'dummy uid'
        DUMMY_ADDR = b'\xfd\x02\xec\xeeby~u\xd8k\xcf\xf1d.\xb0\x84J\xfb(\xc7'

        event = {'args': {
            'amount': DUMMY_AMOUNT,
            'uid': DUMMY_UID,
            'depositor': DUMMY_ADDR,
        }}

        child_chain.apply_deposit(event)

        tx = child_chain.current_block.transaction_set[0]
        assert tx.amount == DUMMY_AMOUNT
        assert tx.uid == DUMMY_UID
        assert tx.new_owner == eth_utils.normalize_address(DUMMY_ADDR)

    def test_submit_block(self, child_chain):
        DUMMY_MERKLE = 'merkle hash'
        MOCK_TRANSACT = mock()

        block_number = child_chain.current_block_number
        block = child_chain.current_block
        when(child_chain.current_block).merklize_transaction_set().thenReturn(DUMMY_MERKLE)
        when(self.ROOT_CHAIN).transact(any).thenReturn(MOCK_TRANSACT)

        child_chain.submit_block(self.DUMMY_SIG)

        verify(MOCK_TRANSACT).submitBlock(DUMMY_MERKLE, block_number)
        assert child_chain.current_block_number == block_number + 1
        assert child_chain.blocks[block_number] == block
        assert child_chain.current_block == Block()

    def test_submit_block_with_invalid_sig(self, child_chain):
        INVALID_SIG = '11' * 65
        with pytest.raises(InvalidBlockSignatureException):
            child_chain.submit_block(INVALID_SIG)

    def test_submit_block_with_empty_sig(self, child_chain):
        EMPTY_SIG = '00' * 65
        with pytest.raises(InvalidBlockSignatureException):
            child_chain.submit_block(EMPTY_SIG)

    def test_apply_transaction(self, child_chain):
        DUMMY_TX_KEY = b'8b76243a95f959bf101248474e6bdacdedc8ad995d287c24616a41bd51642965'

        tx = Transaction(prev_block=1, uid=1, amount=10, new_owner=self.DUMMY_TX_NEW_OWNER)
        tx.sign(eth_utils.normalize_key(DUMMY_TX_KEY))

        child_chain.apply_transaction(rlp.encode(tx).hex())

        prev_tx = child_chain.blocks[1].transaction_set[0]
        assert child_chain.current_block.transaction_set[0] == tx
        assert prev_tx.new_owner == tx.sender
        assert prev_tx.amount == tx.amount
        assert prev_tx.spent is True

    def test_apply_transaction_with_previous_tx_not_exist(self, child_chain):
        DUMMY_TX_KEY = b'8b76243a95f959bf101248474e6bdacdedc8ad995d287c24616a41bd51642965'

        # token with uid 3 doesn't exist
        tx = Transaction(prev_block=1, uid=3, amount=10, new_owner=self.DUMMY_TX_NEW_OWNER)
        tx.sign(eth_utils.normalize_key(DUMMY_TX_KEY))

        with pytest.raises(PreviousTxNotFoundException):
            child_chain.apply_transaction(rlp.encode(tx).hex())

    def test_apply_transaction_with_double_spending(self, child_chain):
        DUMMY_TX_KEY = b'8b76243a95f959bf101248474e6bdacdedc8ad995d287c24616a41bd51642965'

        tx = Transaction(prev_block=1, uid=1, amount=10, new_owner=self.DUMMY_TX_NEW_OWNER)
        tx.sign(eth_utils.normalize_key(DUMMY_TX_KEY))

        child_chain.apply_transaction(rlp.encode(tx).hex())

        # try to spend a spent transaction
        with pytest.raises(TxAlreadySpentException):
            child_chain.apply_transaction(rlp.encode(tx).hex())

    def test_apply_transaction_with_mismatch_amount(self, child_chain):
        DUMMY_TX_KEY = b'8b76243a95f959bf101248474e6bdacdedc8ad995d287c24616a41bd51642965'

        # token with uid 1 doesn't have 20
        tx = Transaction(prev_block=1, uid=1, amount=20, new_owner=self.DUMMY_TX_NEW_OWNER)
        tx.sign(eth_utils.normalize_key(DUMMY_TX_KEY))

        with pytest.raises(TxAmountMismatchException):
            child_chain.apply_transaction(rlp.encode(tx).hex())

    def test_apply_transaction_with_invalid_sig(self, child_chain):
        DUMMY_INVALID_TX_KEY = b'7a76243a95f959bf101248474e6bdacdedc8ad995d287c24616a41bd51642965'

        tx = Transaction(prev_block=1, uid=1, amount=10, new_owner=self.DUMMY_TX_NEW_OWNER)
        tx.sign(eth_utils.normalize_key(DUMMY_INVALID_TX_KEY))

        with pytest.raises(InvalidTxSignatureException):
            child_chain.apply_transaction(rlp.encode(tx).hex())

    def test_get_current_block(self, child_chain):
        expected = rlp.encode(child_chain.current_block).hex()
        assert expected == child_chain.get_current_block()

    def test_get_block(self, child_chain):
        DUMMY_BLK_NUM = 1

        expected = rlp.encode(child_chain.blocks[DUMMY_BLK_NUM]).hex()
        assert expected == child_chain.get_block(DUMMY_BLK_NUM)

    def test_get_proof(self, child_chain):
        DUMMY_BLK_NUM = 1
        DUMMY_UID = 1

        block = child_chain.blocks[DUMMY_BLK_NUM]
        block.merklize_transaction_set()
        expected_proof = block.merkle.create_merkle_proof(DUMMY_UID)
        assert expected_proof == child_chain.get_proof(DUMMY_BLK_NUM, DUMMY_UID)
