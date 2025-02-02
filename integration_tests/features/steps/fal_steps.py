from functools import reduce
import os
from behave import *
from fal.cli import cli
import tempfile
import json
import unittest
from os.path import exists
from pathlib import Path
import re

MODELS = ["agent_wait_time", "zendesk_ticket_data"]


@given("`{command}` is run")
def run_command_step(context, command):
    _run_command(command)


@when("`{command}` is run")
def run_command_step2(context, command):
    _run_command(command)


@given("the project {project}")
def set_project_folder(context, project):
    context.base_dir = reduce(os.path.join, [os.getcwd(), "projects", project])
    context.temp_dir = tempfile.TemporaryDirectory()
    os.environ["temp_dir"] = context.temp_dir.name


@when("the data is seeded")
def seed_data(context):
    base_path = Path(context.base_dir)
    profiles_dir = str(base_path.parent.absolute())
    os.system(f"dbt seed --profiles-dir {profiles_dir} --project-dir {base_path}")


@when("the following command is invoked")
def invoke_fal_flow(context):
    profiles_dir = Path(context.base_dir).parent.absolute()
    args = context.text.replace("$baseDir", context.base_dir)
    args = args.replace("$profilesDir", str(profiles_dir))
    cli(args.split(" "))


@then("the following scripts are ran")
def check_script_results(context):
    expected_scripts = context.table.headings
    for script in expected_scripts:
        _assertScriptFileExists(context, script)


@then("no models are calculated")
def no_models_are_run(context):
    fal_results = _get_fal_results_file_name(context)
    fal_results_paths = list(
        map(lambda file: os.path.join(context.temp_dir.name, file), fal_results)
    )
    for fal_result_path in fal_results_paths:
        if exists(fal_result_path):
            data = json.load(open(fal_result_path))
            assert len(data["results"]) == 0
        else:
            assert True


@then("no scripts are run")
def no_scripts_are_run(context):
    assert len(os.listdir(context.temp_dir.name)) == 0


@then("the following models are calculated")
def check_model_results(context):
    fal_results = _get_fal_results_file_name(context)
    calculated_results = reduce(
        lambda prev, fal_result: prev.append(
            _get_models_from_result(context.temp_dir.name, fal_result)
        )
        or prev,
        fal_results,
        [],
    )
    unittest.TestCase().assertCountEqual(
        _flatten_list(calculated_results), context.table.headings
    )


@then("scripts are run for {model}")
def check_run_step(context, model):
    output = open("mock/temp/output", "r").read()

    if model == "all models":
        for m in MODELS:
            assert m in output
    else:
        assert model in output


@then("{model} scripts are skipped")
def check_no_run_step(context, model):
    output = open("mock/temp/output", "r").read()
    if model == "all model":
        for m in MODELS:
            assert m not in output
    else:
        assert model not in output


@then("outputs for {model} contain {run_type} results")
def check_outputs(context, model, run_type):
    test_results = run_type == "test"
    if model == "all models":
        for m in MODELS:
            _check_output(m, test_results)
    else:
        _check_output(model, test_results)


def _assertScriptFileExists(context, script):
    script_file = os.path.join(context.temp_dir.name, script)
    assert exists(script_file)


def _run_command(command: str):
    os.system(f"cd mock && {command} > temp/output")


def _check_output(model, is_test=False):
    try:
        print(f"Checking: {model}", flush=True)
        if is_test:
            expected = open(f"mock/fal_output/{model}_expected_test", "r").read()
            current = open(f"mock/temp/{model}_test", "r").read()
        else:
            expected = open(f"mock/fal_output/{model}_expected", "r").read()
            current = open(f"mock/temp/{model}", "r").read()
        assert expected == current
    except AssertionError:
        print(f"Error for {model}:", flush=True)
        print(f"Expected: {expected}", flush=True)
        print(f"Got: {current}", flush=True)
        raise Exception("Did not get expected output")


def _get_models_from_result(dir_name, file_name):
    return list(
        map(
            lambda result: result["unique_id"].split(".")[2],
            _load_result(dir_name, file_name),
        )
    )


def _load_result(dir_name, file_name):
    return json.load(
        open(
            reduce(
                os.path.join,
                [dir_name, "target", file_name],
            )
        )
    )["results"]


def _get_fal_results_file_name(context):
    target_path = os.path.join(context.temp_dir.name, "target")
    pattern = re.compile("fal_results_*.\\.json")
    target_files = list(os.walk(target_path))[0][2]
    return list(filter(lambda file: pattern.match(file), target_files))


def _flatten_list(target_list):
    flat_list = []
    for element in target_list:
        if type(element) is list:
            for item in element:
                flat_list.append(item)
        else:
            flat_list.append(element)
    return flat_list
