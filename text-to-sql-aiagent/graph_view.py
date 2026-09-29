from pipeline.graph import build_graph

app = build_graph()

# option 1: print ascii representation in terminal
print(app.get_graph().draw_ascii())

# option 2: save a proper diagram as an image (needs internet, uses mermaid.ink)
app.get_graph().draw_mermaid_png(output_file_path="graph.png")