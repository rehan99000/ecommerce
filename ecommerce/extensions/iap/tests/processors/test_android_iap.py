# -*- coding: utf-8 -*-
"""Unit tests of Android IAP payment processor implementation."""


from urllib.parse import urljoin

import ddt
import mock
from django.conf import settings
from django.test import RequestFactory
from django.urls import reverse
from oscar.apps.payment.exceptions import GatewayError
from oscar.core.loading import get_model
from testfixtures import LogCapture

from ecommerce.core.url_utils import get_ecommerce_url
from ecommerce.extensions.checkout.utils import get_receipt_page_url
from ecommerce.extensions.iap.processors.android_iap import AndroidIAP
from ecommerce.extensions.iap.api.v1.google_validator import GooglePlayValidator
from ecommerce.extensions.payment.tests.processors.mixins import PaymentProcessorTestCaseMixin
from ecommerce.tests.testcases import TestCase

PaymentProcessorResponse = get_model('payment', 'PaymentProcessorResponse')


@ddt.ddt
class AndroidIAPTests(PaymentProcessorTestCaseMixin, TestCase):
    """
    Tests for the AndroidIAP payment processor.
    """

    processor_class = AndroidIAP
    processor_name = 'android-iap'

    @classmethod
    def setUpClass(cls):
        """
        Class set up - setting static up paypal sdk configuration to be used in test methods
        """
        super(AndroidIAPTests, cls).setUpClass()  # required to pass CI build
        android_iap_configuration = settings.PAYMENT_PROCESSOR_CONFIG['edx']['android-iap']

    def setUp(self):
        """
        setUp method
        """
        super(AndroidIAPTests, self).setUp()

        # Dummy request from which an HTTP Host header can be extracted during
        # construction of absolute URLs
        self.request = RequestFactory().post('/')
        self.processor_response_log = (
            u"Failed to execute AndroidInAppPurchase payment on attempt [{attempt_count}]. "
            u"AndroidInAppPurchase's response was recorded in entry [{entry_id}]."
        )
        self.RETURN_DATA = {
            'transactionId': 'transactionId.android.test.purchased',
            'productId': 'android.test.purchased',
            'purchaseToken': 'inapp:org.edx.mobile:android.test.purchased',
        }

    def _get_receipt_url(self):
        """
        DRY helper for getting receipt page URL.
        """
        return get_receipt_page_url(site_configuration=self.site.siteconfiguration)

    def test_get_transaction_parameters(self):
        """
        Verify the processor returns the appropriate parameters required to complete a transaction.
        """
        expected = {
            'payment_page_url': urljoin(get_ecommerce_url(), reverse('iap:iap-execute')),
        }
        actual = self.processor.get_transaction_parameters(self.basket)
        self.assertEqual(actual, expected)

    @mock.patch.object(GooglePlayValidator, 'validate')
    def test_handle_processor_response_error(self, mock_google_validator):
        """
        Verify that the processor creates the appropriate PaymentEvent and Source objects.
        """
        mock_google_validator.return_value = {
            'error': 'Invalid receipt'
        }
        product_id = self.RETURN_DATA.get('productId')

        logger_name = 'ecommerce.extensions.iap.processors.android_iap'
        with LogCapture(logger_name) as android_iap_logger:
            with self.assertRaises(GatewayError):
                handled_response = self.processor.handle_processor_response(self.RETURN_DATA, basket=self.basket)
                self.assert_processor_response_recorded(self.processor_name, handled_response.get('error'), basket=self.basket)
                ppr = PaymentProcessorResponse.objects.filter(
                    processor_name=self.processor_name
                ).latest('created')
                android_iap_logger.check_present(
                    (
                        logger_name,
                        'WARNING',
                        "Failed to execute android IAP payment for [{}] on attempt [{}]. "
                        "Andoid IAP's response was recorded in entry [{}].".format(
                            product_id,
                            1,
                            ppr.id
                        ),
                    ),
                    (
                        logger_name,
                        'ERROR',
                        "Failed to execute android IAP payment for [%s]. "
                        "Android IAP's response was recorded in entry [%d].".format(
                            product_id,
                            ppr.id
                        ),
                    ),
                )

    @mock.patch.object(GooglePlayValidator, 'validate')
    def test_handle_processor_response(self, mock_google_validator):
        """
        Verify that the processor creates the appropriate PaymentEvent and Source objects.
        """
        mock_google_validator.return_value = {
            'resource': {
                'orderId': 'orderId.android.test.purchased'
            }
        }

        handled_response = self.processor.handle_processor_response(self.RETURN_DATA, basket=self.basket)
        self.assertEqual(handled_response.currency, self.basket.currency)
        self.assertEqual(handled_response.total, self.basket.total_incl_tax)
        self.assertEqual(handled_response.transaction_id, self.RETURN_DATA['transactionId'])
        self.assertIsNone(handled_response.card_type)

    def test_issue_credit(self):
        """
        Tests issuing credit/refund with AndroidInAppPurchase processor.
        """
        self.assertRaises(NotImplementedError, self.processor.issue_credit, None, None, None, None, None)

    def test_issue_credit_error(self):
        """
        Tests issuing credit/refund with AndroidInAppPurchase processor.
        """
        self.assertRaises(NotImplementedError, self.processor.issue_credit, None, None, None, None, None)
