import logging
from typing import Mapping, Optional, Union

from ruamel.yaml import YAML

from great_expectations.data_context.data_context.abstract_data_context import (
    AbstractDataContext,
)
from great_expectations.data_context.types.base import DataContextConfig
from great_expectations.data_context.types.data_context_variables import (
    FileDataContextVariables,
)

logger = logging.getLogger(__name__)

# TODO: check if this can be refactored to use YAMLHandler class
yaml = YAML()
yaml.indent(mapping=2, sequence=4, offset=2)
yaml.default_flow_style = False


class FileDataContext(AbstractDataContext):
    """
    Extends AbstractDataContext, contains only functionality necessary to hydrate state from disk.

    TODO: Most of the functionality in DataContext will be refactored into this class, and the current DataContext
    class will exist only for backwards-compatibility reasons.
    """

    def __init__(
        self,
        project_config: Union[DataContextConfig, Mapping],
        context_root_dir: Optional[str] = None,
        runtime_environment: Optional[dict] = None,
    ) -> None:
        """FileDataContext constructor

        Args:
            project_config (DataContextConfig):  Config for current DataContext
            context_root_dir (Optional[str]): location to look for the ``great_expectations.yml`` file. If None,
                searches for the file based on conventions for project subdirectories.
            runtime_environment (Optional[dict]): a dictionary of config variables that override both those set in
                config_variables.yml and the environment
        """
        super().__init__(runtime_environment=runtime_environment)
        self._context_root_directory = context_root_dir
        self._project_config = self._apply_global_config_overrides(
            config=project_config
        )

    def _init_variables(self) -> FileDataContextVariables:
        raise NotImplementedError

    @property
    def root_directory(self) -> str:
        """The root directory for configuration objects in the data context; the location in which
        ``great_expectations.yml`` is located."""
        return self._context_root_directory
