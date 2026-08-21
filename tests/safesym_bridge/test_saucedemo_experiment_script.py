import pytest

from ai_web_explorer.grounded_web.stagehand_actions import StagehandObservedAction
from scripts import run_saucedemo_open_exploration_observe_act as experiment


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_saucedemo_script_supplies_cart_action_when_observe_cannot_locate_it(
    monkeypatch,
):
    async def observe_returns_no_action(provider, instruction):
        return []

    monkeypatch.setattr(
        experiment,
        "_original_observe_action",
        observe_returns_no_action,
    )

    actions = await experiment._observe_action_with_saucedemo_overrides(
        object(),
        "Open the shopping cart. Target: Cart icon in the header.",
    )

    assert actions == [
        StagehandObservedAction(
            description="SauceDemo shopping cart link",
            selector='[data-test="shopping-cart-link"]',
            method="click",
        )
    ]


@pytest.mark.anyio
async def test_saucedemo_script_leaves_unrelated_actions_unchanged(monkeypatch):
    expected = [
        StagehandObservedAction(
            description="Sort products",
            selector='[data-test="product-sort-container"]',
            method="selectOptionFromDropdown",
            arguments=("lohi",),
        )
    ]

    async def observe_returns_action(provider, instruction):
        return expected

    monkeypatch.setattr(
        experiment,
        "_original_observe_action",
        observe_returns_action,
    )

    actions = await experiment._observe_action_with_saucedemo_overrides(
        object(),
        "Sort the product list. Target: Sort dropdown.",
    )

    assert actions == expected


@pytest.mark.anyio
async def test_saucedemo_script_does_not_open_cart_for_add_to_cart(monkeypatch):
    expected = [
        StagehandObservedAction(
            description="Add Sauce Labs Backpack to cart",
            selector='[data-test="add-to-cart-sauce-labs-backpack"]',
            method="click",
        )
    ]

    async def observe_returns_add_action(provider, instruction):
        return expected

    monkeypatch.setattr(
        experiment,
        "_original_observe_action",
        observe_returns_add_action,
    )

    actions = await experiment._observe_action_with_saucedemo_overrides(
        object(),
        "Add a product to the shopping cart. Target: Add to cart button.",
    )

    assert actions == expected


@pytest.mark.anyio
async def test_saucedemo_script_supplies_public_password(monkeypatch):
    async def observe_returns_placeholder(provider, instruction):
        return [
            StagehandObservedAction(
                description="Password field",
                selector='[data-test="password"]',
                method="fill",
                arguments=("your_password_here",),
            )
        ]

    monkeypatch.setattr(
        experiment,
        "_original_observe_action",
        observe_returns_placeholder,
    )

    actions = await experiment._observe_action_with_saucedemo_overrides(
        object(),
        "Input the password in the Password field. Target: Password field.",
    )

    assert actions == [
        StagehandObservedAction(
            description="Password field",
            selector='[data-test="password"]',
            method="fill",
            arguments=("secret_sauce",),
        )
    ]


@pytest.mark.anyio
async def test_saucedemo_script_replaces_placeholder_username(monkeypatch):
    async def observe_returns_placeholder(provider, instruction):
        return [
            StagehandObservedAction(
                description="Username field",
                selector='[data-test="username"]',
                method="fill",
                arguments=("your_username_here",),
            )
        ]

    monkeypatch.setattr(
        experiment,
        "_original_observe_action",
        observe_returns_placeholder,
    )

    actions = await experiment._observe_action_with_saucedemo_overrides(
        object(),
        "Input the username field.",
    )

    assert actions[0].arguments == ("standard_user",)


@pytest.mark.anyio
async def test_saucedemo_provider_factory_binds_site_overrides(monkeypatch):
    class FakeProvider:
        pass

    provider = FakeProvider()

    async def create_provider(**kwargs):
        return provider

    async def observe_returns_placeholder(bound_provider, instruction):
        return [
            StagehandObservedAction(
                description="Password field",
                selector='[data-test="password"]',
                method="fill",
                arguments=("your_password_here",),
            )
        ]

    monkeypatch.setattr(experiment, "_original_create_provider", create_provider)
    monkeypatch.setattr(
        experiment,
        "_original_observe_action",
        observe_returns_placeholder,
    )

    result = await experiment._create_saucedemo_provider()
    actions = await result.observe_action("Input the password field.")

    assert actions[0].arguments == ("secret_sauce",)
