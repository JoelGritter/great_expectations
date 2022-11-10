from pprint import pprint

import pandas as pd
import pytest

from great_expectations.core import (
    ExpectationConfiguration,
    ExpectationValidationResult,
)
from great_expectations.core.batch import Batch
from great_expectations.core.util import convert_to_json_serializable
from great_expectations.execution_engine import (
    PandasExecutionEngine,
    SqlAlchemyExecutionEngine,
)
from great_expectations.expectations.core import ExpectColumnValuesToBeInSet
from great_expectations.expectations.metrics import (
    ColumnMax,
    ColumnValuesNonNull,
    CompoundColumnsUnique,
)
from great_expectations.expectations.metrics.map_metric_provider import (
    ColumnMapMetricProvider,
    MapMetricProvider,
)
from great_expectations.validator.validation_graph import MetricConfiguration
from great_expectations.validator.validator import Validator


@pytest.fixture
def dataframe_for_unexpected_rows():
    return pd.DataFrame(
        {
            "a": [1, 5, 22, 3, 5, 10],
            "b": ["cat", "fish", "dog", "giraffe", "lion", "zebra"],
        }
    )


@pytest.fixture
def pandas_dataframe_for_unexpected_rows_with_index():
    return pd.DataFrame(
        {
            "pk_1": [0, 1, 2, 3, 4, 5],
            "pk_2": ["zero", "one", "two", "three", "four", "five"],
            "numbers_with_duplicates": [1, 5, 22, 3, 5, 10],
            "animal_names_no_duplicates": [
                "cat",
                "fish",
                "dog",
                "giraffe",
                "lion",
                "zebra",
            ],
        }
    )


@pytest.fixture()
def expected_evr_without_unexpected_rows():
    return ExpectationValidationResult(
        success=False,
        expectation_config={
            "expectation_type": "expect_column_values_to_be_in_set",
            "kwargs": {
                "column": "a",
                "value_set": [1, 5, 22],
            },
            "meta": {},
        },
        result={
            "element_count": 6,
            "unexpected_count": 2,
            "unexpected_index_list": [3, 5],
            "unexpected_percent": 33.33333333333333,
            "partial_unexpected_list": [3, 10],
            "unexpected_list": [3, 10],
            "partial_unexpected_index_list": [3, 5],
            "partial_unexpected_counts": [
                {"value": 3, "count": 1},
                {"value": 10, "count": 1},
            ],
            "missing_count": 0,
            "missing_percent": 0.0,
            "unexpected_percent_total": 33.33333333333333,
            "unexpected_percent_nonmissing": 33.33333333333333,
        },
        exception_info={
            "raised_exception": False,
            "exception_traceback": None,
            "exception_message": None,
        },
        meta={},
    )


def test_get_table_metric_provider_metric_dependencies(empty_sqlite_db):
    mp = ColumnMax()
    metric = MetricConfiguration("column.max", {}, {})
    dependencies = mp.get_evaluation_dependencies(
        metric, execution_engine=SqlAlchemyExecutionEngine(engine=empty_sqlite_db)
    )
    assert dependencies["metric_partial_fn"].id[0] == "column.max.aggregate_fn"

    mp = ColumnMax()
    metric = MetricConfiguration("column.max", {}, {})
    dependencies = mp.get_evaluation_dependencies(
        metric, execution_engine=PandasExecutionEngine()
    )

    table_column_types_metric: MetricConfiguration = dependencies["table.column_types"]
    table_columns_metric: MetricConfiguration = dependencies["table.columns"]
    table_row_count_metric: MetricConfiguration = dependencies["table.row_count"]
    assert dependencies == {
        "table.column_types": table_column_types_metric,
        "table.columns": table_columns_metric,
        "table.row_count": table_row_count_metric,
    }
    assert dependencies["table.columns"].id == (
        "table.columns",
        (),
        (),
    )


def test_get_aggregate_count_aware_metric_dependencies(basic_spark_df_execution_engine):
    mp = ColumnValuesNonNull()
    metric = MetricConfiguration("column_values.nonnull.unexpected_count", {}, {})
    dependencies = mp.get_evaluation_dependencies(
        metric, execution_engine=PandasExecutionEngine()
    )
    assert (
        dependencies["unexpected_condition"].id[0] == "column_values.nonnull.condition"
    )

    metric = MetricConfiguration("column_values.nonnull.unexpected_count", {}, {})
    dependencies = mp.get_evaluation_dependencies(
        metric, execution_engine=basic_spark_df_execution_engine
    )
    assert (
        dependencies["metric_partial_fn"].id[0]
        == "column_values.nonnull.unexpected_count.aggregate_fn"
    )

    metric = MetricConfiguration(
        "column_values.nonnull.unexpected_count.aggregate_fn", {}, {}
    )
    dependencies = mp.get_evaluation_dependencies(metric)
    assert (
        dependencies["unexpected_condition"].id[0] == "column_values.nonnull.condition"
    )


def test_get_map_metric_dependencies():
    mp = ColumnMapMetricProvider()
    metric = MetricConfiguration("foo.unexpected_count", {}, {})
    dependencies = mp.get_evaluation_dependencies(metric)
    assert dependencies["unexpected_condition"].id[0] == "foo.condition"

    metric = MetricConfiguration("foo.unexpected_rows", {}, {})
    dependencies = mp.get_evaluation_dependencies(metric)
    assert dependencies["unexpected_condition"].id[0] == "foo.condition"

    metric = MetricConfiguration("foo.unexpected_values", {}, {})
    dependencies = mp.get_evaluation_dependencies(metric)
    assert dependencies["unexpected_condition"].id[0] == "foo.condition"

    metric = MetricConfiguration("foo.unexpected_value_counts", {}, {})
    dependencies = mp.get_evaluation_dependencies(metric)
    assert dependencies["unexpected_condition"].id[0] == "foo.condition"

    metric = MetricConfiguration("foo.unexpected_index_list", {}, {})
    dependencies = mp.get_evaluation_dependencies(metric)
    assert dependencies["unexpected_condition"].id[0] == "foo.condition"


def test_is_sqlalchemy_metric_selectable():
    assert MapMetricProvider.is_sqlalchemy_metric_selectable(
        map_metric_provider=CompoundColumnsUnique
    )

    assert not MapMetricProvider.is_sqlalchemy_metric_selectable(
        map_metric_provider=ColumnValuesNonNull
    )


def test_pandas_unexpected_rows_basic_result_format(dataframe_for_unexpected_rows):
    expectationConfiguration = ExpectationConfiguration(
        expectation_type="expect_column_values_to_be_in_set",
        kwargs={
            "column": "b",
            "mostly": 0.9,
            "value_set": ["cat", "fish", "dog", "giraffe"],
            "result_format": {
                "result_format": "BASIC",
                "include_unexpected_rows": True,
            },
        },
    )

    expectation = ExpectColumnValuesToBeInSet(expectationConfiguration)
    batch = Batch(data=dataframe_for_unexpected_rows)
    engine = PandasExecutionEngine()
    validator = Validator(
        execution_engine=engine,
        batches=[
            batch,
        ],
    )
    result = expectation.validate(validator)

    assert convert_to_json_serializable(result.result) == {
        "element_count": 6,
        "unexpected_count": 2,
        "unexpected_percent": 33.33333333333333,
        "partial_unexpected_list": ["lion", "zebra"],
        "missing_count": 0,
        "missing_percent": 0.0,
        "unexpected_percent_total": 33.33333333333333,
        "unexpected_percent_nonmissing": 33.33333333333333,
        "unexpected_rows": [{"a": 5, "b": "lion"}, {"a": 10, "b": "zebra"}],
    }


def test_pandas_unexpected_rows_summary_result_format_unexpected_rows_explicitly_false(
    dataframe_for_unexpected_rows,
):
    expectationConfiguration = ExpectationConfiguration(
        expectation_type="expect_column_values_to_be_in_set",
        kwargs={
            "column": "b",
            "mostly": 0.9,
            "value_set": ["cat", "fish", "dog", "giraffe"],
            "result_format": {
                "result_format": "SUMMARY",
                "include_unexpected_rows": False,  # this is the default value, but making explicit for testing purposes
            },
        },
    )

    expectation = ExpectColumnValuesToBeInSet(expectationConfiguration)
    batch = Batch(data=dataframe_for_unexpected_rows)
    engine = PandasExecutionEngine()
    validator = Validator(
        execution_engine=engine,
        batches=[
            batch,
        ],
    )
    result = expectation.validate(validator)

    assert convert_to_json_serializable(result.result) == {
        "element_count": 6,
        "unexpected_count": 2,
        "unexpected_percent": 33.33333333333333,
        "partial_unexpected_counts": [
            {"count": 1, "value": "lion"},
            {"count": 1, "value": "zebra"},
        ],
        "partial_unexpected_index_list": [4, 5],
        "partial_unexpected_list": ["lion", "zebra"],
        "missing_count": 0,
        "missing_percent": 0.0,
        "unexpected_percent_total": 33.33333333333333,
        "unexpected_percent_nonmissing": 33.33333333333333,
    }


def test_pandas_unexpected_rows_summary_result_format_unexpected_rows_including_unexpected_rows(
    dataframe_for_unexpected_rows,
):
    expectationConfiguration = ExpectationConfiguration(
        expectation_type="expect_column_values_to_be_in_set",
        kwargs={
            "column": "b",
            "mostly": 0.9,
            "value_set": ["cat", "fish", "dog", "giraffe"],
            "result_format": {
                "result_format": "SUMMARY",
                "include_unexpected_rows": True,
            },
        },
    )

    expectation = ExpectColumnValuesToBeInSet(expectationConfiguration)
    batch = Batch(data=dataframe_for_unexpected_rows)
    engine = PandasExecutionEngine()
    validator = Validator(
        execution_engine=engine,
        batches=[
            batch,
        ],
    )
    result = expectation.validate(validator)

    assert convert_to_json_serializable(result.result) == {
        "element_count": 6,
        "unexpected_count": 2,
        "unexpected_percent": 33.33333333333333,
        "partial_unexpected_counts": [
            {"count": 1, "value": "lion"},
            {"count": 1, "value": "zebra"},
        ],
        "partial_unexpected_index_list": [4, 5],
        "partial_unexpected_list": ["lion", "zebra"],
        "missing_count": 0,
        "missing_percent": 0.0,
        "unexpected_percent_total": 33.33333333333333,
        "unexpected_percent_nonmissing": 33.33333333333333,
        "unexpected_rows": [{"a": 5, "b": "lion"}, {"a": 10, "b": "zebra"}],
    }


def test_pandas_unexpected_rows_complete_result_format(dataframe_for_unexpected_rows):
    expectationConfiguration = ExpectationConfiguration(
        expectation_type="expect_column_values_to_be_in_set",
        kwargs={
            "column": "a",
            "value_set": [1, 5, 22],
            "result_format": {
                "result_format": "COMPLETE",
                "include_unexpected_rows": True,
            },
        },
    )

    expectation = ExpectColumnValuesToBeInSet(expectationConfiguration)
    batch = Batch(data=dataframe_for_unexpected_rows)
    engine = PandasExecutionEngine()
    validator = Validator(
        execution_engine=engine,
        batches=[
            batch,
        ],
    )
    result = expectation.validate(validator)
    assert convert_to_json_serializable(result.result) == {
        "element_count": 6,
        "unexpected_count": 2,
        "unexpected_index_list": [3, 5],
        "unexpected_percent": 33.33333333333333,
        "partial_unexpected_list": [3, 10],
        "unexpected_list": [3, 10],
        "unexpected_rows": [{"a": 3, "b": "giraffe"}, {"a": 10, "b": "zebra"}],
        "partial_unexpected_index_list": [3, 5],
        "partial_unexpected_counts": [
            {"value": 3, "count": 1},
            {"value": 10, "count": 1},
        ],
        "missing_count": 0,
        "missing_percent": 0.0,
        "unexpected_percent_total": 33.33333333333333,
        "unexpected_percent_nonmissing": 33.33333333333333,
    }


def test_pandas_default_unexpected_index_columns_complete_result_format(
    pandas_dataframe_for_unexpected_rows_with_index: pd.DataFrame,
):
    expectationConfiguration = ExpectationConfiguration(
        expectation_type="expect_column_values_to_be_in_set",
        kwargs={
            "column": "numbers_with_duplicates",
            "value_set": [1, 5, 22],
            "result_format": {
                "result_format": "COMPLETE",
            },
        },
    )

    expectation = ExpectColumnValuesToBeInSet(expectationConfiguration)
    batch: Batch = Batch(data=pandas_dataframe_for_unexpected_rows_with_index)
    engine = PandasExecutionEngine()
    validator = Validator(
        execution_engine=engine,
        batches=[
            batch,
        ],
    )
    result = expectation.validate(validator)
    pprint(convert_to_json_serializable(result.result))
    assert convert_to_json_serializable(result.result) == {
        "element_count": 6,
        "unexpected_count": 2,
        "unexpected_index_list": [
            3,
            5,
        ],  # Default pandas index applied, compatible with existing functionality (list of ints)
        "partial_unexpected_index_list": [3, 5],
        "unexpected_percent": 33.33333333333333,
        "partial_unexpected_list": [3, 10],
        "unexpected_list": [3, 10],
        "partial_unexpected_counts": [
            {"value": 3, "count": 1},
            {"value": 10, "count": 1},
        ],
        "missing_count": 0,
        "missing_percent": 0.0,
        "unexpected_percent_total": 33.33333333333333,
        "unexpected_percent_nonmissing": 33.33333333333333,
    }


def test_pandas_single_unexpected_index_columns_complete_result_format(
    pandas_dataframe_for_unexpected_rows_with_index: pd.DataFrame,
):
    expectationConfiguration = ExpectationConfiguration(
        expectation_type="expect_column_values_to_be_in_set",
        kwargs={
            "column": "numbers_with_duplicates",
            "value_set": [1, 5, 22],
            "result_format": {
                "result_format": "COMPLETE",
                "unexpected_index_columns": ["pk_1"],  # Single column
            },
        },
    )

    expectation = ExpectColumnValuesToBeInSet(expectationConfiguration)
    batch: Batch = Batch(data=pandas_dataframe_for_unexpected_rows_with_index)
    engine = PandasExecutionEngine()
    validator = Validator(
        execution_engine=engine,
        batches=[
            batch,
        ],
    )
    result = expectation.validate(validator)
    pprint(convert_to_json_serializable(result.result))
    assert convert_to_json_serializable(result.result) == {
        "element_count": 6,
        "unexpected_count": 2,
        "unexpected_index_list": [
            {
                "pk_1": 3,
            },
            {
                "pk_1": 5,
            },
        ],  # Dicts since a column was provided
        "partial_unexpected_index_list": [
            {
                "pk_1": 3,
            },
            {
                "pk_1": 5,
            },
        ],  # Dicts since a column was provided
        "unexpected_percent": 33.33333333333333,
        "partial_unexpected_list": [3, 10],
        "unexpected_list": [3, 10],
        "partial_unexpected_counts": [
            {"value": 3, "count": 1},
            {"value": 10, "count": 1},
        ],
        "missing_count": 0,
        "missing_percent": 0.0,
        "unexpected_percent_total": 33.33333333333333,
        "unexpected_percent_nonmissing": 33.33333333333333,
    }


def test_pandas_multiple_unexpected_index_columns_complete_result_format(
    pandas_dataframe_for_unexpected_rows_with_index: pd.DataFrame,
):
    expectationConfiguration = ExpectationConfiguration(
        expectation_type="expect_column_values_to_be_in_set",
        kwargs={
            "column": "numbers_with_duplicates",
            "value_set": [1, 5, 22],
            "result_format": {
                "result_format": "COMPLETE",
                "unexpected_index_columns": ["pk_1", "pk_2"],  # Multiple columns
            },
        },
    )

    expectation = ExpectColumnValuesToBeInSet(expectationConfiguration)
    batch: Batch = Batch(data=pandas_dataframe_for_unexpected_rows_with_index)
    engine = PandasExecutionEngine()
    validator = Validator(
        execution_engine=engine,
        batches=[
            batch,
        ],
    )
    result = expectation.validate(validator)
    pprint(convert_to_json_serializable(result.result))
    assert convert_to_json_serializable(result.result) == {
        "element_count": 6,
        "unexpected_count": 2,
        "unexpected_index_list": [
            {"pk_1": 3, "pk_2": "three"},
            {"pk_1": 5, "pk_2": "five"},
        ],  # Dicts since columns were provided
        "partial_unexpected_index_list": [
            {"pk_1": 3, "pk_2": "three"},
            {"pk_1": 5, "pk_2": "five"},
        ],  # Dicts since columns were provided
        "unexpected_percent": 33.33333333333333,
        "partial_unexpected_list": [3, 10],
        "unexpected_list": [3, 10],
        "partial_unexpected_counts": [
            {"value": 3, "count": 1},
            {"value": 10, "count": 1},
        ],
        "missing_count": 0,
        "missing_percent": 0.0,
        "unexpected_percent_total": 33.33333333333333,
        "unexpected_percent_nonmissing": 33.33333333333333,
    }


def test_pandas_multiple_unexpected_index_columns_summary_result_format(
    pandas_dataframe_for_unexpected_rows_with_index: pd.DataFrame,
):
    """
    SUMMARY does include unexpected_index_list. Let's get this right
    Args:
        pandas_dataframe_for_unexpected_rows_with_index ():

    Returns:

    """
    expectationConfiguration = ExpectationConfiguration(
        expectation_type="expect_column_values_to_be_in_set",
        kwargs={
            "column": "numbers_with_duplicates",
            "value_set": [1, 5, 22],
            "result_format": {
                "result_format": "SUMMARY",
                "unexpected_index_columns": ["pk_1", "pk_2"],  # Multiple columns
            },
        },
    )

    expectation = ExpectColumnValuesToBeInSet(expectationConfiguration)
    batch: Batch = Batch(data=pandas_dataframe_for_unexpected_rows_with_index)
    engine = PandasExecutionEngine()
    validator = Validator(
        execution_engine=engine,
        batches=[
            batch,
        ],
    )
    result = expectation.validate(validator)
    assert convert_to_json_serializable(result.result) == {
        "element_count": 6,
        "unexpected_count": 2,
        "partial_unexpected_index_list": [
            {"pk_1": 3, "pk_2": "three"},
            {"pk_1": 5, "pk_2": "five"},
        ],  # Dicts since columns were provided
        "unexpected_percent": 33.33333333333333,
        "partial_unexpected_list": [3, 10],
        "partial_unexpected_counts": [
            {"value": 3, "count": 1},
            {"value": 10, "count": 1},
        ],
        "missing_count": 0,
        "missing_percent": 0.0,
        "unexpected_percent_total": 33.33333333333333,
        "unexpected_percent_nonmissing": 33.33333333333333,
    }


def test_pandas_multiple_unexpected_index_columns_basic_result_format(
    pandas_dataframe_for_unexpected_rows_with_index: pd.DataFrame,
):
    """
    BASIC does not include unexpected_index_list
    """
    expectationConfiguration = ExpectationConfiguration(
        expectation_type="expect_column_values_to_be_in_set",
        kwargs={
            "column": "numbers_with_duplicates",
            "value_set": [1, 5, 22],
            "result_format": {
                "result_format": "BASIC",
                "unexpected_index_columns": ["pk_1", "pk_2"],  # Multiple columns
            },
        },
    )

    expectation = ExpectColumnValuesToBeInSet(expectationConfiguration)
    batch: Batch = Batch(data=pandas_dataframe_for_unexpected_rows_with_index)
    engine = PandasExecutionEngine()
    validator = Validator(
        execution_engine=engine,
        batches=[
            batch,
        ],
    )
    result = expectation.validate(validator)
    assert convert_to_json_serializable(result.result) == {
        "element_count": 6,
        "unexpected_count": 2,
        "unexpected_percent": 33.33333333333333,
        "partial_unexpected_list": [3, 10],
        "missing_count": 0,
        "missing_percent": 0.0,
        "unexpected_percent_total": 33.33333333333333,
        "unexpected_percent_nonmissing": 33.33333333333333,
    }


def test_pandas_single_unexpected_index_columns_complete_result_format_non_existing_column(
    pandas_dataframe_for_unexpected_rows_with_index: pd.DataFrame,
):
    expectationConfiguration = ExpectationConfiguration(
        expectation_type="expect_column_values_to_be_in_set",
        kwargs={
            "column": "numbers_with_duplicates",
            "value_set": [1, 5, 22],
            "result_format": {
                "result_format": "COMPLETE",
                "unexpected_index_columns": ["i_dont_exist"],  # Single column
            },
        },
    )

    expectation = ExpectColumnValuesToBeInSet(expectationConfiguration)
    batch: Batch = Batch(data=pandas_dataframe_for_unexpected_rows_with_index)
    engine = PandasExecutionEngine()
    validator = Validator(
        execution_engine=engine,
        batches=[
            batch,
        ],
    )
    result = expectation.validate(validator)
    assert result.success is False
    assert result.exception_info
    assert (
        result.exception_info["exception_message"]
        == 'Error: The unexpected_index_column: "i_dont_exist" in does not exist in Dataframe. Please check your configuration and try again.'
    )


def test_pandas_multiple_unexpected_index_columns_complete_result_format_non_existing_column(
    pandas_dataframe_for_unexpected_rows_with_index: pd.DataFrame,
):
    expectationConfiguration = ExpectationConfiguration(
        expectation_type="expect_column_values_to_be_in_set",
        kwargs={
            "column": "numbers_with_duplicates",
            "value_set": [1, 5, 22],
            "result_format": {
                "result_format": "COMPLETE",
                "unexpected_index_columns": [
                    "pk_1",
                    "i_dont_exist",
                ],  # Only 1 column is valid
            },
        },
    )
    expectation = ExpectColumnValuesToBeInSet(expectationConfiguration)
    batch: Batch = Batch(data=pandas_dataframe_for_unexpected_rows_with_index)
    engine = PandasExecutionEngine()
    validator = Validator(
        execution_engine=engine,
        batches=[
            batch,
        ],
    )
    result = expectation.validate(validator)
    assert result.success is False
    assert result.exception_info
    assert (
        result.exception_info["exception_message"]
        == 'Error: The unexpected_index_column: "i_dont_exist" in does not exist in Dataframe. Please check your configuration and try again.'
    )


def test_pandas_default_to_not_include_unexpected_rows(
    dataframe_for_unexpected_rows, expected_evr_without_unexpected_rows
):
    expectation_configuration = ExpectationConfiguration(
        expectation_type="expect_column_values_to_be_in_set",
        kwargs={
            "column": "a",
            "value_set": [1, 5, 22],
            "result_format": {
                "result_format": "COMPLETE",
            },
        },
    )

    expectation = ExpectColumnValuesToBeInSet(expectation_configuration)
    batch = Batch(data=dataframe_for_unexpected_rows)
    engine = PandasExecutionEngine()
    validator = Validator(
        execution_engine=engine,
        batches=[
            batch,
        ],
    )
    result = expectation.validate(validator)
    assert result.result == expected_evr_without_unexpected_rows.result


def test_pandas_specify_not_include_unexpected_rows(
    dataframe_for_unexpected_rows, expected_evr_without_unexpected_rows
):
    expectationConfiguration = ExpectationConfiguration(
        expectation_type="expect_column_values_to_be_in_set",
        kwargs={
            "column": "a",
            "value_set": [1, 5, 22],
            "result_format": {
                "result_format": "COMPLETE",
                "include_unexpected_rows": False,
            },
        },
    )

    expectation = ExpectColumnValuesToBeInSet(expectationConfiguration)
    batch = Batch(data=dataframe_for_unexpected_rows)
    engine = PandasExecutionEngine()
    validator = Validator(
        execution_engine=engine,
        batches=[
            batch,
        ],
    )
    result = expectation.validate(validator)
    assert result.result == expected_evr_without_unexpected_rows.result


def test_include_unexpected_rows_without_explicit_result_format_raises_error(
    dataframe_for_unexpected_rows,
):
    expectationConfiguration = ExpectationConfiguration(
        expectation_type="expect_column_values_to_be_in_set",
        kwargs={
            "column": "a",
            "value_set": [1, 5, 22],
            "result_format": {
                "include_unexpected_rows": False,
            },
        },
    )

    expectation = ExpectColumnValuesToBeInSet(expectationConfiguration)
    batch = Batch(data=dataframe_for_unexpected_rows)
    engine = PandasExecutionEngine()
    validator = Validator(
        execution_engine=engine,
        batches=[
            batch,
        ],
    )
    with pytest.raises(ValueError):
        expectation.validate(validator)
