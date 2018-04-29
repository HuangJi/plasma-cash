import pytest
from mockito import patch

from plasma_cash.child_chain.transaction import Transaction
from unit_tests.unstub_mixin import UnstubMixin


class TestTransaction(UnstubMixin):

    @pytest.fixture(scope='function')
    def tx(self):
        DUMMY_TX_OWNER = b'\x8cT\xa4\xa0\x17\x9f$\x80\x1fI\xf92-\xab<\x87\xeb\x19L\x9b'
        return Transaction(
            prev_block=0,
            uid=1,
            amount=10,
            new_owner=DUMMY_TX_OWNER
        )

    def test_constructor(self):
        PREV_BLOCK = 1
        UID = 'uid'
        AMOUNT = 1
        NEW_OWNER = 'new owner'
        SIG = 'sig'
        tx = Transaction(
            prev_block=PREV_BLOCK,
            uid=UID,
            amount=AMOUNT,
            new_owner=NEW_OWNER,
            sig=SIG
        )

        assert tx.prev_block == PREV_BLOCK
        assert tx.uid == UID
        assert tx.amount == AMOUNT
        assert tx.new_owner == NEW_OWNER
        assert tx.sig == SIG
        assert tx.spent is False

    def test_constructor_default_empty_sig(self):
        DUMMY_TX_OWNER = b'\x8cT\xa4\xa0\x17\x9f$\x80\x1fI\xf92-\xab<\x87\xeb\x19L\x9b'
        tx = Transaction(
            prev_block=0,
            uid=1,
            amount=10,
            new_owner=DUMMY_TX_OWNER
        )
        assert tx.sig == b'\x00' * 65

    def test_hash(self, tx):
        TX_HASH = (b'\xc40\x9f&\x9e\xd5\xda\xc4\xa8\xee\xe24[\x0c\x88P\xc7'
                   b'\x14\x1f2\x84\xefe\xf8\xcc\xe3^"I\r\t\\')

        assert tx.hash == TX_HASH

    def test_merkle_hash(self, tx):
        MERKLE_HASH = (b'\xaai8\x00\x9fJ \xde\xb8<h\x97S\x1d\x9d\xf6y\xfb\x8a'
                       b'\x98\x1e\xcb\t\xcb\x08\n\xd1\r6\x85\x0b\x19')
        assert tx.merkle_hash == MERKLE_HASH

    def test_sign(self, tx):
        SIGNATURE = 'signature'
        DUMMY_KEY = 'key'

        def sign_func(hash, key):
            if hash == tx.hash and key == DUMMY_KEY:
                return SIGNATURE
            raise Exception('unexpected input to patch sign_func')

        patch('plasma_cash.child_chain.transaction.sign', sign_func)
        tx.sign(DUMMY_KEY)
        assert tx.sig == SIGNATURE
