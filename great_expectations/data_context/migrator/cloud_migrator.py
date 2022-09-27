"""TODO: Add docstring"""
import logging
import warnings
from dataclasses import dataclass
from typing import List, Optional

import requests

from great_expectations.core.configuration import AbstractConfig
from great_expectations.core.http import create_session
from great_expectations.data_context.data_context.abstract_data_context import (
    AbstractDataContext,
)
from great_expectations.data_context.data_context.base_data_context import (
    BaseDataContext,
)
from great_expectations.data_context.data_context.cloud_data_context import (
    CloudDataContext,
)
from great_expectations.data_context.migrator.configuration_bundle import (
    ConfigurationBundle,
    ConfigurationBundleJsonSerializer,
    ConfigurationBundleSchema,
)
from great_expectations.data_context.store.ge_cloud_store_backend import (
    AnyPayload,
    construct_json_payload,
    construct_url,
    get_user_friendly_error_message,
)
from great_expectations.data_context.types.resource_identifiers import (
    ValidationResultIdentifier,
)
from great_expectations.exceptions.exceptions import GeCloudError

logger = logging.getLogger(__name__)


@dataclass
class SendValidationResultsErrorDetails:
    # TODO: Implementation
    pass


class CloudMigrator:
    def __init__(
        self,
        context: BaseDataContext,
        ge_cloud_base_url: Optional[str] = None,
        ge_cloud_access_token: Optional[str] = None,
        ge_cloud_organization_id: Optional[str] = None,
    ) -> None:
        self._context = context

        cloud_config = CloudDataContext.get_ge_cloud_config(
            ge_cloud_base_url=ge_cloud_base_url,
            ge_cloud_access_token=ge_cloud_access_token,
            ge_cloud_organization_id=ge_cloud_organization_id,
        )

        ge_cloud_base_url = cloud_config.base_url
        ge_cloud_access_token = cloud_config.access_token
        ge_cloud_organization_id = cloud_config.organization_id

        # Invariant due to `get_ge_cloud_config` raising an error if any config values are missing
        if not ge_cloud_organization_id:
            raise ValueError(
                "An organization id must be present when performing a migration"
            )

        self._ge_cloud_base_url = ge_cloud_base_url
        self._ge_cloud_access_token = ge_cloud_access_token
        self._ge_cloud_organization_id = ge_cloud_organization_id

        self._session = create_session(access_token=ge_cloud_access_token)

    @classmethod
    def migrate(
        cls,
        context: BaseDataContext,
        test_migrate: bool,
        ge_cloud_base_url: Optional[str] = None,
        ge_cloud_access_token: Optional[str] = None,
        ge_cloud_organization_id: Optional[str] = None,
    ) -> None:
        """Migrate your Data Context to GX Cloud.

        Args:
            context: The Data Context you wish to migrate.
            test_migrate: True if this is a test, False if you want to perform
                the migration.
            ge_cloud_base_url: Optional, you may provide this alternatively via
                environment variable GE_CLOUD_BASE_URL
            ge_cloud_access_token: Optional, you may provide this alternatively
                via environment variable GE_CLOUD_ACCESS_TOKEN
            ge_cloud_organization_id: Optional, you may provide this alternatively
                via environment variable GE_CLOUD_ORGANIZATION_ID

        Returns:
            None
        """
        raise NotImplementedError("This will be implemented soon!")
        # This code will be uncommented when the migrator is implemented:
        # cloud_migrator: CloudMigrator = cls(
        #     context=context,
        #     ge_cloud_base_url=ge_cloud_base_url,
        #     ge_cloud_access_token=ge_cloud_access_token,
        #     ge_cloud_organization_id=ge_cloud_organization_id,
        # )
        # cloud_migrator._migrate_to_cloud(test_migrate)

    @classmethod
    def migrate_validation_result(
        cls,
        context: AbstractDataContext,
        validation_result_suite_identifier: ValidationResultIdentifier,
        ge_cloud_base_url: Optional[str] = None,
        ge_cloud_access_token: Optional[str] = None,
        ge_cloud_organization_id: Optional[str] = None,
    ):
        raise NotImplementedError("This will be implemented soon!")

    def _migrate_to_cloud(self, test_migrate: bool):
        """TODO: This is a rough outline of the steps to take during the migration, verify against the spec before release."""
        self._print_migration_introduction_message()
        if test_migrate:
            self._warn_about_test_migrate()

        configuration_bundle: ConfigurationBundle = ConfigurationBundle(
            context=self._context
        )

        if not configuration_bundle.is_usage_stats_enabled():
            self._warn_about_usage_stats_disabled()

        self._print_configuration_bundle_summary(configuration_bundle)

        if not test_migrate:
            configuration_bundle_serializer = ConfigurationBundleJsonSerializer(
                schema=ConfigurationBundleSchema()
            )
            configuration_bundle_response: AnyPayload = self._send_configuration_bundle(
                configuration_bundle, configuration_bundle_serializer
            )
            self._print_send_configuration_bundle_error(configuration_bundle_response)
            self._break_for_send_configuration_bundle_error(
                configuration_bundle_response
            )

        errors: List[
            SendValidationResultsErrorDetails
        ] = self._send_and_print_validation_results(test_migrate)
        self._print_validation_result_error_summary(errors)
        self._print_migration_conclusion_message()

    def _warn_about_test_migrate(self) -> None:
        warnings.warn(
            "This is a test run! Please pass `test_migrate=False` to begin the "
            "actual migration (e.g. `CloudMigrator.migrate(context=context, test_migrate=False)`)."
        )

    def _warn_about_usage_stats_disabled(self) -> None:
        warnings.warn(
            "We noticed that you had disabled usage statistics tracking. "
            "Please note that by migrating your context to GX Cloud your new Cloud Data Context "
            "will emit usage statistics. These statistics help us understand how we can improve "
            "the product and we hope you don't mind!"
        )

    def _build_configuration_bundle(self) -> ConfigurationBundle:
        pass

    def _print_configuration_bundle_summary(
        self, configuration_bundle: ConfigurationBundle
    ) -> None:
        self._print("Bundling context configuration (step 1/4)")

        to_print = (
            ("Datasource", configuration_bundle.datasources),
            ("Checkpoint", configuration_bundle.checkpoints),
            ("Expectation Suite", configuration_bundle.expectation_suites),
            ("Profiler", configuration_bundle.profilers),
        )

        for name, collection in to_print:
            self._print_object_summary(obj_name=name, obj_collection=collection)

    def _print_object_summary(
        self, obj_name: str, obj_collection: List[AbstractConfig]
    ) -> None:
        length = len(obj_collection)
        self._print(f"Bundled {length} {obj_name}s:", indent=2)
        for obj in obj_collection[:10]:
            self._print(obj.name, indent=4)

        if length > 10:
            self._print(
                f"({length-10} other {obj_name.lower()} not displayed)", indent=4
            )

    def _send_configuration_bundle(
        self,
        configuration_bundle: ConfigurationBundle,
        serializer: ConfigurationBundleJsonSerializer,
    ) -> AnyPayload:
        url = construct_url(
            base_url=self._ge_cloud_base_url,
            organization_id=self._ge_cloud_organization_id,
            resource_name="migration",
        )

        serialized_bundle = serializer.serialize(configuration_bundle)
        data = construct_json_payload(
            resource_type="migration",
            organization_id=self._ge_cloud_organization_id,
            attributes_key="bundle",
            attributes_value=serialized_bundle,
        )

        try:
            response = self._session.post(url, json=data)
            response.raise_for_status()
            return response.json()

        except requests.HTTPError as http_exc:
            raise GeCloudError(
                f"Unable to migrate config to Cloud: {get_user_friendly_error_message(http_exc)}"
            )
        except requests.Timeout as timeout_exc:
            logger.exception(timeout_exc)
            raise GeCloudError(
                "Unable to migrate config to Cloud: This is likely a transient error. Please try again."
            )
        except Exception as e:
            logger.warning(str(e))
            raise GeCloudError(f"Something went wrong while migrating to Cloud: {e}")

    def _print_send_configuration_bundle_error(self, http_response: AnyPayload) -> None:
        pass

    def _break_for_send_configuration_bundle_error(
        self, http_response: AnyPayload
    ) -> None:
        pass

    def _send_and_print_validation_results(
        self, test_migrate: bool
    ) -> List[SendValidationResultsErrorDetails]:
        # TODO: Uses migrate_validation_result in a loop. Only sends if not self.test_migrate
        pass

    def _print_validation_result_error_summary(
        self, errors: List[SendValidationResultsErrorDetails]
    ) -> None:
        pass

    def _print_migration_introduction_message(self) -> None:
        self._print("Thank you for using Great Expectations!")
        self._print("We will now begin the migration process to GX Cloud.")
        self._print(
            "First, we will bundle your existing context configuration and send it to the Cloud backend."
        )
        self._print("Then, we will send each of your validation results.")

    def _print_migration_conclusion_message(self) -> None:
        self._print("Success!")
        self._print(
            "Now that you have migrated your Data Context to GX Cloud, you should use your CloudDataContext from now on to interact with Great Expectations."
        )
        self._print(
            "If you continue to use your existing Data Context your configurations could become out of sync."
        )

    def _print(self, text: str, indent: int = 0) -> None:
        print(f"{indent * ' '}{text}")