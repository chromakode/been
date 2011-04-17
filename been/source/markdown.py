from been.core import DirectorySource, source_registry

class Markdown(DirectorySource):
    kind = 'markdown'
    def process_event(self, event):
        lines = event['content'].splitlines()
        event['title'] = lines[0]
        event['content'] = "\n".join(lines[1:])
        event['summary'] = event['content']
        return event
source_registry.add(Markdown)
