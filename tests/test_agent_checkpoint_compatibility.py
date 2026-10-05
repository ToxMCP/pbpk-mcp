"""Both persistence backends survive a real graph invocation and resume."""
import pytest
from mcp_bridge.agent.langchain_scaffolding import build_agent_graph, create_initial_agent_state

@pytest.mark.parametrize('sqlite', [False, True])
def test_graph_checkpoint_roundtrip(tmp_path, sqlite):
    graph = build_agent_graph(
        planner_node=lambda state: state,
        tool_selection_node=lambda state: state,
        confirmation_node=lambda state: {},
        tool_execution_node=lambda state: state,
        response_synthesis_node=lambda state: {**state, 'last_tool_result': 'checkpoint-tested'},
        checkpointer_path=str(tmp_path/'checkpoint.sqlite') if sqlite else None,
    )
    config = {'configurable': {'thread_id': 'maintenance-checkpoint-test'}}
    result = graph.invoke(create_initial_agent_state(), config)
    assert result['last_tool_result'] == 'checkpoint-tested'
    assert graph.get_state(config).values['last_tool_result'] == 'checkpoint-tested'
    assert graph.invoke(None, config)['last_tool_result'] == 'checkpoint-tested'
