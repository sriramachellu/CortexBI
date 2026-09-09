import logging

from packages.agents.state import AgentState

logger = logging.getLogger("cortexbi.agents.graph")

PIPELINE_NODES = [
    "intake", "validation", "cleaning", "eda",
    "target_framing", "modeling", "explainability",
    "dashboard_builder",
]


async def run_pipeline(state: AgentState, *, storage, db_session) -> AgentState:
    from packages.agents.nodes.cleaning import cleaning_node
    from packages.agents.nodes.dashboard_builder import dashboard_builder_node
    from packages.agents.nodes.eda import eda_node
    from packages.agents.nodes.explainability import explainability_node
    from packages.agents.nodes.intake import intake_node
    from packages.agents.nodes.modeling import modeling_node
    from packages.agents.nodes.target_framing import target_framing_node
    from packages.agents.nodes.validation import validation_node

    node_funcs = {
        "intake": intake_node,
        "validation": validation_node,
        "cleaning": cleaning_node,
        "eda": eda_node,
        "target_framing": target_framing_node,
        "modeling": modeling_node,
        "explainability": explainability_node,
        "dashboard_builder": dashboard_builder_node,
    }

    for node_name in PIPELINE_NODES:
        logger.info("running node: %s", node_name)
        func = node_funcs[node_name]
        state = await func(state, storage=storage, db_session=db_session)

        if state.get("status") == "failed":
            logger.error("pipeline failed at node %s: %s", node_name, state.get("error"))
            break

    return state
