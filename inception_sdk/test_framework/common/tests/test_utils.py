# standard libs
import logging
from unittest import TestCase, mock

# inception sdk
from inception_sdk.tools.common.tools_utils import override_logging_level

with override_logging_level(logging.WARNING):
    from black import format_str
    from black.mode import Mode

# inception sdk
import inception_sdk.test_framework.common.utils as utils


class CommonUtilsTest(TestCase):
    def setUp(self) -> None:
        self.maxDiff = None
        return super().setUp()

    def test_replace_flag_definition_ids_in_list_parameter(self):
        flag_mapping = {
            "REPAYMENT_HOLIDAY": "E2E_REPAYMENT_HOLIDAY",
            "US_SAVINGS_ACCOUNT_TIER_UPPER": "E2E_US_SAVINGS_ACCOUNT_TIER_UPPER",
            "example1": "E2E_example1",
        }

        # flags in list
        list_parameter = {"flag_key": ["REPAYMENT_HOLIDAY", "example1"]}
        expected_list_parameter = ["E2E_REPAYMENT_HOLIDAY", "E2E_example1"]
        list_result = utils.replace_flags_in_parameter(
            list_parameter,
            flag_mapping,
        )
        self.assertEqual(list_result, expected_list_parameter)

    def test_replace_flag_definition_ids_in_single_level_json_parameter(self):
        flag_mapping = {
            "REPAYMENT_HOLIDAY": "E2E_REPAYMENT_HOLIDAY",
            "US_SAVINGS_ACCOUNT_TIER_UPPER": "E2E_US_SAVINGS_ACCOUNT_TIER_UPPER",
            "example1": "E2E_example1",
        }

        # flags in json with one level
        json_parameter_single_level = {
            "flag_key": {"US_SAVINGS_ACCOUNT_TIER_UPPER": "500", "example1": "500"}
        }
        expected_json_parameter_single_level = {
            "E2E_US_SAVINGS_ACCOUNT_TIER_UPPER": "500",
            "E2E_example1": "500",
        }
        json_result_single = utils.replace_flags_in_parameter(
            json_parameter_single_level,
            flag_mapping,
        )
        self.assertEqual(json_result_single, expected_json_parameter_single_level)

    def test_replace_flag_ids_in_multi_level_json_parameter(self):
        flag_mapping = {
            "REPAYMENT_HOLIDAY": "E2E_REPAYMENT_HOLIDAY",
            "US_SAVINGS_ACCOUNT_TIER_UPPER": "E2E_US_SAVINGS_ACCOUNT_TIER_UPPER",
            "example1": "E2E_example1",
        }

        # flags in json with multiple levels but only one level replaced
        json_parameter_multi_level = {
            "flag_key": {
                "US_SAVINGS_ACCOUNT_TIER_UPPER": {"flag_key": {"example1": "500"}},
                "US_SAVINGS_ACCOUNT_TIER_LOWER": {"flag_key": {"example2": "500"}},
            }
        }
        expected_json_parameter_multi_level = {
            "E2E_US_SAVINGS_ACCOUNT_TIER_UPPER": {"E2E_example1": "500"},
            "US_SAVINGS_ACCOUNT_TIER_LOWER": {"example2": "500"},
        }
        json_result_multi = utils.replace_flags_in_parameter(
            json_parameter_multi_level,
            flag_mapping,
        )
        self.assertEqual(json_result_multi, expected_json_parameter_multi_level)

    def test_replace_flag_ids_in_complex_multi_level_json_parameter(self):
        flag_mapping = {
            "REPAYMENT_HOLIDAY": "E2E_REPAYMENT_HOLIDAY",
            "US_SAVINGS_ACCOUNT_TIER_UPPER": "E2E_US_SAVINGS_ACCOUNT_TIER_UPPER",
            "US_SAVINGS_ACCOUNT_TIER_LOWER": "E2E_US_SAVINGS_ACCOUNT_TIER_LOWER",
            "US_SAVINGS_ACCOUNT_TIER_MIDDLE": "E2E_US_SAVINGS_ACCOUNT_TIER_MIDDLE",
            "example1": "E2E_example1",
        }

        # flags in json with multiple levels but only one level replaced
        # this is not representative of a real use-case, but is to catch flag_keys
        # at multiple levels
        json_parameter_multi_level = {
            "flag_key": {
                "US_SAVINGS_ACCOUNT_TIER_UPPER": {
                    "flag_key": {
                        "example1": "500",
                        "example2": "200",  # example2 is not in mapping so should be unchanged
                    },
                    "example3": "300",
                    "example4": {"flag_key": {"example1": "500"}},
                },
                "US_SAVINGS_ACCOUNT_TIER_LOWER": {
                    "flag_key": {"example2": "500"}  # again, example2 is not in mapping
                },
                "US_SAVINGS_ACCOUNT_TIER_MIDDLE": {"example5": "500"},
            }
        }
        expected_json_parameter_multi_level = {
            "E2E_US_SAVINGS_ACCOUNT_TIER_UPPER": {
                "E2E_example1": "500",
                "example2": "200",
                "example3": "300",
                "example4": {"E2E_example1": "500"},
            },
            "E2E_US_SAVINGS_ACCOUNT_TIER_LOWER": {"example2": "500"},
            "E2E_US_SAVINGS_ACCOUNT_TIER_MIDDLE": {"example5": "500"},
        }
        json_result_multi = utils.replace_flags_in_parameter(
            json_parameter_multi_level,
            flag_mapping,
        )
        self.assertEqual(json_result_multi, expected_json_parameter_multi_level)

    def test_replace_flags_in_dict_empty_dict(self):
        flag_mapping = {
            "REPAYMENT_HOLIDAY": "E2E_REPAYMENT_HOLIDAY",
            "US_SAVINGS_ACCOUNT_TIER_UPPER": "E2E_US_SAVINGS_ACCOUNT_TIER_UPPER",
            "example1": "E2E_example1",
        }

        value_dict = {}
        result = utils._replace_flags_in_dict(value_dict, flag_mapping)
        self.assertEqual(result, value_dict)

    def test_replace_flags_in_dict_no_flag_key(self):
        flag_mapping = {
            "REPAYMENT_HOLIDAY": "E2E_REPAYMENT_HOLIDAY",
            "US_SAVINGS_ACCOUNT_TIER_UPPER": "E2E_US_SAVINGS_ACCOUNT_TIER_UPPER",
            "example1": "E2E_example1",
        }

        value_dict = {"US_SAVINGS_ACCOUNT_TIER_UPPER": "200"}

        expected_result = {"E2E_US_SAVINGS_ACCOUNT_TIER_UPPER": "200"}

        result = utils._replace_flags_in_dict(value_dict, flag_mapping)
        self.assertEqual(result, expected_result)

    def test_replace_flags_in_dict_nested_flag_key(self):
        flag_mapping = {
            "REPAYMENT_HOLIDAY": "E2E_REPAYMENT_HOLIDAY",
            "US_SAVINGS_ACCOUNT_TIER_UPPER": "E2E_US_SAVINGS_ACCOUNT_TIER_UPPER",
            "example1": "E2E_example1",
        }

        value_dict = {
            "US_SAVINGS_ACCOUNT_TIER_UPPER": "200",
            "US_SAVINGS_ACCOUNT_TIER_LOWER": {"flag_key": {"example1": "500"}},
        }

        expected_result = {
            "E2E_US_SAVINGS_ACCOUNT_TIER_UPPER": "200",
            "US_SAVINGS_ACCOUNT_TIER_LOWER": {"E2E_example1": "500"},
        }

        result = utils._replace_flags_in_dict(value_dict, flag_mapping)
        self.assertEqual(result, expected_result)

    def test_replace_flags_in_list(self):
        flag_mapping = {
            "REPAYMENT_HOLIDAY": "E2E_REPAYMENT_HOLIDAY",
            "US_SAVINGS_ACCOUNT_TIER_UPPER": "E2E_US_SAVINGS_ACCOUNT_TIER_UPPER",
            "example1": "E2E_example1",
        }

        value_list = ["REPAYMENT_HOLIDAY", "example1"]

        expected_result = ["E2E_REPAYMENT_HOLIDAY", "E2E_example1"]

        list_result = utils._replace_flags_in_list(value_list, flag_mapping)
        self.assertEqual(list_result, expected_result)

    def test_get_nested_dict_keys_flat_dict(self):
        dictionary = {"k1": "v1"}
        expected_result = ["k1"]
        actual_result = list(utils._get_nested_dict_keys(dictionary))
        self.assertEqual(actual_result, expected_result)

    def test_get_nested_dict_keys_nested_dict(self):
        dictionary = {
            "k1": "v1",
            "k2": {"k3": "v3", "k4": {"k5": "v5"}},
            "k6": "v6",
        }
        expected_result = ["k1", "k2", "k3", "k4", "k5", "k6"]
        actual_result = list(utils._get_nested_dict_keys(dictionary))
        self.assertEqual(actual_result, expected_result)


LINE_SEP = "\n"


class IdentifyCLUDependenciesTest(TestCase):
    @classmethod
    def setUpClass(cls):
        # Mocking this to have fixed test assertions and make tests work across different platforms
        # Otherwise we'd have varying outcomes and would pollute assertions with len(os.linesep)
        # Using patcher approach as PropertyMock doesn't seem to be possible with decorator syntax
        cls.patcher = mock.patch.object(utils, "os")
        cls.mock_object = cls.patcher.start()
        type(cls.mock_object).linesep = mock.PropertyMock(return_value=LINE_SEP)
        cls.addClassCleanup(cls.patcher.stop)

        super().setUpClass()

    def test_identify_clu_dependencies_for_single_dep(self):
        resource = "&{my_dep}"
        dependencies = utils.identify_clu_dependencies(resource_id="dummy_id", resource=resource)
        self.assertEqual(
            dependencies,
            [
                utils.ResourceDependency(
                    source_id="dummy_id",
                    target_id="my_dep",
                    start_position=0,
                    end_position=8,
                )
            ],
        )

    def test_identify_clu_dependencies_for_single_dep_with_line_seperators(self):
        resource = LINE_SEP + "&{my_dep}" + LINE_SEP
        dependencies = utils.identify_clu_dependencies(resource_id="dummy_id", resource=resource)
        self.assertEqual(
            dependencies,
            [
                utils.ResourceDependency(
                    source_id="dummy_id",
                    target_id="my_dep",
                    start_position=1,
                    end_position=9,
                )
            ],
        )

    def test_identify_clu_dependencies_for_multiple_dep(self):
        resource = LINE_SEP + "&{my_dep}" + LINE_SEP + "blablal&{my_dep_2}"
        dependencies = utils.identify_clu_dependencies(resource_id="dummy_id", resource=resource)
        self.assertEqual(
            dependencies,
            [
                utils.ResourceDependency(
                    source_id="dummy_id",
                    target_id="my_dep",
                    start_position=1,
                    end_position=9,
                ),
                utils.ResourceDependency(
                    source_id="dummy_id",
                    target_id="my_dep_2",
                    start_position=18,
                    end_position=28,
                ),
            ],
        )

    def test_identify_clu_dependencies_with_dep_over_multiple_lines(self):
        resource = "&{" + LINE_SEP + "my_dep" + LINE_SEP + "}"
        with self.assertRaises(ValueError) as ctx:
            utils.identify_clu_dependencies(resource_id="dummy_id", resource=resource)
        self.assertEqual(
            ctx.exception.args[0],
            "Dependency reference split across lines in resource `dummy_id` at position `2`",
        )

    def test_identify_clu_dependencies_for_repeated_dep(self):
        resource = LINE_SEP + "&{my_dep}" + LINE_SEP + "blablal&{my_dep}"
        dependencies = utils.identify_clu_dependencies(resource_id="dummy_id", resource=resource)
        self.assertEqual(
            dependencies,
            [
                utils.ResourceDependency(
                    source_id="dummy_id",
                    target_id="my_dep",
                    start_position=1,
                    end_position=9,
                ),
                utils.ResourceDependency(
                    source_id="dummy_id",
                    target_id="my_dep",
                    start_position=18,
                    end_position=26,
                ),
            ],
        )

    def test_identify_clu_dependencies_with_nested_dep(self):
        resource = "&{&{my_dep}}"
        with self.assertRaises(ValueError) as ctx:
            utils.identify_clu_dependencies(resource_id="dummy_id", resource=resource)
        self.assertEqual(
            ctx.exception.args[0],
            "Nested dependency reference in resource `dummy_id` at position `3`",
        )

    def test_identify_clu_dependencies_with_field_id_syntax(self):
        resource = "&{my_dep:field}}"
        with self.assertRaises(ValueError) as ctx:
            utils.identify_clu_dependencies(resource_id="dummy_id", resource=resource)
        self.assertEqual(
            ctx.exception.args[0],
            "Reference `my_dep:field` contains `resource_id:resource_field` CLU syntax "
            "that is not yet supported by our tooling",
        )


@mock.patch.object(utils, "identify_clu_dependencies")
class ReplaceCLUDependenciesTest(TestCase):
    def test_replace_clu_dependency(self, identify_clu_dependencies_mock: mock.Mock):
        #             2           3    4          15
        resource = "bla" + LINE_SEP + "&{target_id}" + LINE_SEP
        identify_clu_dependencies_mock.return_value = [
            utils.ResourceDependency("source_id", "target_id", 4, 15)
        ]
        mapping = {"target_id": "mapped_target_id"}

        modified_resource = utils.replace_clu_dependencies("source_id", resource, mapping)

        self.assertEqual(modified_resource, "bla" + LINE_SEP + "mapped_target_id" + LINE_SEP)

    def test_replace_clu_dependencies(self, identify_clu_dependencies_mock: mock.Mock):
        #             2           3    4          15          16     19    20           33
        resource = "bla" + LINE_SEP + "&{target_id}" + LINE_SEP + "bla" + "&{target_id_2}"
        identify_clu_dependencies_mock.return_value = [
            utils.ResourceDependency("source_id", "target_id", 4, 15),
            utils.ResourceDependency("source_id", "target_id_2", 20, 33),
        ]
        mapping = {"target_id": "mapped_target_id", "target_id_2": "mapped_target_id_2"}

        modified_resource = utils.replace_clu_dependencies("source_id", resource, mapping)

        self.assertEqual(
            modified_resource,
            "bla" + LINE_SEP + "mapped_target_id" + LINE_SEP + "bla" + "mapped_target_id_2",
        )

    def test_replace_repeated_clu_dependencies(self, identify_clu_dependencies_mock: mock.Mock):
        #             2           3    4          15          16     19    20         31
        resource = "bla" + LINE_SEP + "&{target_id}" + LINE_SEP + "bla" + "&{target_id}"
        identify_clu_dependencies_mock.return_value = [
            utils.ResourceDependency("source_id", "target_id", 4, 15),
            utils.ResourceDependency("source_id", "target_id", 20, 31),
        ]
        mapping = {"target_id": "mapped_target_id"}

        modified_resource = utils.replace_clu_dependencies("source_id", resource, mapping)

        self.assertEqual(
            modified_resource,
            "bla" + LINE_SEP + "mapped_target_id" + LINE_SEP + "bla" + "mapped_target_id",
        )

    def test_replace_with_duplicate_mappings(self, identify_clu_dependencies_mock: mock.Mock):
        mapping_1 = {"target_id": "mapped_target_id_a", "target_id_2": "mapped_target_id_2"}
        mapping_2 = {"target_id_3": "mapped_target_id_3", "target_id": "mapped_target_id_b"}
        with self.assertRaises(utils.CLUDuplicateResourceId) as ctx:
            utils.replace_clu_dependencies("source_id", "", mapping_1, mapping_2)
        self.assertEqual(
            ctx.exception.__cause__.args[0],
            "Duplicate resource ids found across id mappings for different resource types: "
            "{'target_id': ['mapped_target_id_a', 'mapped_target_id_b']}",
        )

    def test_replace_with_missing_mappings_no_remove_clu_syntax(
        self, identify_clu_dependencies_mock: mock.Mock
    ):
        #             2           3    4          15
        resource = "bla" + LINE_SEP + "&{target_id}" + LINE_SEP
        identify_clu_dependencies_mock.return_value = [
            utils.ResourceDependency("source_id", "target_id", 4, 15)
        ]
        mapping = {"other_target_id": "mapped_target_id"}

        with self.assertRaises(utils.CLUMissingMapping) as ctx:
            utils.replace_clu_dependencies("source_id", resource, mapping)
        self.assertEqual(
            ctx.exception.args[0],
            "Could not find mapping for CLU reference `target_id`",
        )

    def test_replace_with_empty_mappings_and_remove_clu_syntax(
        self, identify_clu_dependencies_mock: mock.Mock
    ):
        #             2           3    4          15
        resource = "bla" + LINE_SEP + "&{target_id}" + LINE_SEP
        identify_clu_dependencies_mock.return_value = [
            utils.ResourceDependency("source_id", "target_id", 4, 15)
        ]

        modified_resource = utils.replace_clu_dependencies(
            "source_id", resource, remove_clu_syntax_for_unknown_ids=True
        )
        self.assertEqual(modified_resource, "bla" + LINE_SEP + "target_id" + LINE_SEP)

    def test_replace_with_missing_mappings_and_remove_clu_syntax(
        self, identify_clu_dependencies_mock: mock.Mock
    ):
        #             2           3    4          15
        resource = "bla" + LINE_SEP + "&{target_id}" + LINE_SEP
        identify_clu_dependencies_mock.return_value = [
            utils.ResourceDependency("source_id", "target_id", 4, 15)
        ]
        mapping = {"other_target_id": "mapped_target_id"}

        modified_resource = utils.replace_clu_dependencies(
            "source_id", resource, mapping, remove_clu_syntax_for_unknown_ids=True
        )

        self.assertEqual(modified_resource, "bla" + LINE_SEP + "target_id" + LINE_SEP)


class ReplaceScheduleTagIdsTest(TestCase):
    def test_replace_in_event_type_with_single_tag_id(self):
        schedule_tag_mapping = {
            "EVENT_1": "E2E_AST_1",
        }
        result = utils.replace_schedule_tag_ids_in_contract(
            contract_data='event_types = [SmartContractEventType(name="EVENT_1", '
            'scheduler_tag_ids=["TAG_1"])]',
            id_mapping=schedule_tag_mapping,
            default_paused_tag_id="E2E_PAUSED_TAG",
        )
        result = format_str(result, mode=Mode(line_length=100))
        self.assertEqual(
            result,
            'event_types = [SmartContractEventType(name="EVENT_1", '
            'scheduler_tag_ids=["E2E_AST_1"])]\n',
        )

    def test_replace_in_supervisor_event_type_with_single_tag_id(self):
        schedule_tag_mapping = {
            "EVENT_1": "E2E_AST_1",
        }
        result = utils.replace_schedule_tag_ids_in_contract(
            contract_data='event_types = [SupervisorContractEventType(name="EVENT_1", '
            'scheduler_tag_ids=["TAG_1"])]',
            id_mapping=schedule_tag_mapping,
            default_paused_tag_id="E2E_PAUSED_TAG",
        )
        result = format_str(result, mode=Mode(line_length=100))
        self.assertEqual(
            result,
            'event_types = [SupervisorContractEventType(name="EVENT_1", '
            'scheduler_tag_ids=["E2E_AST_1"])]\n',
        )

    def test_replace_in_event_type_with_constant_as_name(self):
        schedule_tag_mapping = {
            "EVENT_1": "E2E_AST_1",
        }
        result = utils.replace_schedule_tag_ids_in_contract(
            contract_data='NAME = "EVENT_1"\n'
            'event_types = [SmartContractEventType(name=NAME, scheduler_tag_ids=["TAG_1"])]',
            id_mapping=schedule_tag_mapping,
            default_paused_tag_id="E2E_PAUSED_TAG",
        )
        result = format_str(result, mode=Mode(line_length=100))
        self.assertEqual(
            result,
            'NAME = "EVENT_1"\n'
            'event_types = [SmartContractEventType(name=NAME, scheduler_tag_ids=["E2E_AST_1"])]\n',
        )

    def test_replace_in_event_type_no_tag_ids(self):
        schedule_tag_mapping = {
            "EVENT_1": "E2E_AST_1",
        }
        result = utils.replace_schedule_tag_ids_in_contract(
            contract_data='event_types=[SmartContractEventType(name="EVENT_1")]',
            id_mapping=schedule_tag_mapping,
            default_paused_tag_id="E2E_PAUSED_TAG",
        )
        result = format_str(result, mode=Mode(line_length=100))
        self.assertEqual(
            result,
            'event_types = [SmartContractEventType(name="EVENT_1", '
            'scheduler_tag_ids=["E2E_AST_1"])]\n',
        )

    def test_replace_in_event_type_multiple_tag_ids(self):
        schedule_tag_mapping = {
            "EVENT_1": "E2E_AST_1",
        }
        result = utils.replace_schedule_tag_ids_in_contract(
            contract_data='event_types=[SmartContractEventType(name="EVENT_1", '
            + 'scheduler_tag_ids=["a", "b"])]',
            id_mapping=schedule_tag_mapping,
            default_paused_tag_id="E2E_PAUSED_TAG",
        )
        result = format_str(result, mode=Mode(line_length=100))
        self.assertEqual(
            result,
            'event_types = [SmartContractEventType(name="EVENT_1", '
            'scheduler_tag_ids=["E2E_AST_1"])]\n',
        )

    def test_replace_in_event_type_using_default_tag(self):
        schedule_tag_mapping = {}

        result = utils.replace_schedule_tag_ids_in_contract(
            contract_data='event_types=[SmartContractEventType(name="EVENT_1", '
            'scheduler_tag_ids=["TAG_1"])]',
            id_mapping=schedule_tag_mapping,
            default_paused_tag_id="E2E_PAUSED_TAG",
        )
        result = format_str(result, mode=Mode(line_length=100))
        self.assertEqual(
            result,
            'event_types = [SmartContractEventType(name="EVENT_1", '
            'scheduler_tag_ids=["E2E_PAUSED_TAG"])]\n',
        )

    def test_replace_in_event_type_doesnt_affect_non_event_type(self):
        schedule_tag_mapping = {}

        result = utils.replace_schedule_tag_ids_in_contract(
            contract_data='event_types=[BlaBla(name="EVENT_1")]',
            id_mapping=schedule_tag_mapping,
            default_paused_tag_id="E2E_PAUSED_TAG",
        )
        result = format_str(result, mode=Mode(line_length=100))
        self.assertEqual(
            result,
            'event_types = [BlaBla(name="EVENT_1")]\n',
        )

    def test_replace_fails_if_event_type_has_no_name(self):
        schedule_tag_mapping = {}

        with self.assertRaises(ValueError) as ctx:
            utils.replace_schedule_tag_ids_in_contract(
                contract_data='SmartContractEventType(scheduler_tag_ids=["TAG_1"])',
                id_mapping=schedule_tag_mapping,
                default_paused_tag_id="E2E_PAUSED_TAG",
            )
        self.assertEqual(
            ctx.exception.args[0],
            "SmartContractEventType/SupervisorContractEventType has no `name` kwarg",
        )

    def test_replace_ignores_if_event_type_name_is_not_name_or_constant(self):
        schedule_tag_mapping = {}

        result = utils.replace_schedule_tag_ids_in_contract(
            contract_data="SmartContractEventType(name=str())",
            id_mapping=schedule_tag_mapping,
            default_paused_tag_id="E2E_PAUSED_TAG",
        )
        self.assertEqual(result, "SmartContractEventType(name=str())")

    def test_replace_ignores_non_name_EventType_func(self):
        schedule_tag_mapping = {}

        result = utils.replace_schedule_tag_ids_in_contract(
            contract_data="SmartContractEventType.abc(name=str())",
            id_mapping=schedule_tag_mapping,
            default_paused_tag_id="E2E_PAUSED_TAG",
        )
        self.assertEqual(result, "SmartContractEventType.abc(name=str())")

    def test_replace_ignores_non_call_EventType(self):
        schedule_tag_mapping = {}

        result = utils.replace_schedule_tag_ids_in_contract(
            contract_data="a = SmartContractEventType",
            id_mapping=schedule_tag_mapping,
            default_paused_tag_id="E2E_PAUSED_TAG",
        )
        result = format_str(result, mode=Mode(line_length=100))
        self.assertEqual(
            result,
            "a = SmartContractEventType\n",
        )


class TestSafeMerge(TestCase):
    def test_safe_merge_with_duplicate_keys(self):
        mapping_1 = {"target_id": "mapped_target_id_a"}
        mapping_2 = {"target_id": "mapped_target_id_b"}
        with self.assertRaises(KeyError) as ctx:
            utils.safe_merge_dicts([mapping_1, mapping_2])
        self.assertEqual(
            ctx.exception.args[0],
            "Duplicate resource ids found across id mappings for different resource types: "
            "{'target_id': ['mapped_target_id_a', 'mapped_target_id_b']}",
        )

    def test_safe_merge_identical_dictionaries(self):
        mapping_1 = {"target_id": "mapped_target_id_a"}
        with self.assertRaises(KeyError) as ctx:
            utils.safe_merge_dicts([mapping_1, mapping_1])
        self.assertEqual(
            ctx.exception.args[0],
            "Duplicate resource ids found across id mappings for different resource types: "
            "{'target_id': ['mapped_target_id_a', 'mapped_target_id_a']}",
        )

    def test_safe_merge_dictionaries_with_overlapping_keys(self):
        mapping_1 = {"target_id": "mapped_target_id_a", "target_id_2": "mapped_target_2_a"}
        mapping_2 = {"target_id": "mapped_target_id_b", "target_id_3": "mapped_target_3_a"}
        with self.assertRaises(KeyError) as ctx:
            utils.safe_merge_dicts([mapping_1, mapping_2])
        self.assertEqual(
            ctx.exception.args[0],
            "Duplicate resource ids found across id mappings for different resource types: "
            "{'target_id': ['mapped_target_id_a', 'mapped_target_id_b']}",
        )
