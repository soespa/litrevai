from langchain_text_splitters import RecursiveCharacterTextSplitter

from litrevai.llm import BaseLLM


def extract_list(text, prompt, chunk_size=4096, chunk_overlap=20, model: BaseLLM | None = None):

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=len,
        is_separator_regex=False,
    )

    splits = text_splitter.split_text(text)

    l = []

    answers = []

    html = ''

    with open('prompts/extract_objectives.txt', 'r') as f:
        system_prompt = f.read()

    for split in tqdm(splits, total=len(splits)):


        messages = [
            {
                'role': 'system',
                'content': system_prompt
            },
            {
                'role': 'user',
                'content': f'Context: {split}'
            }
        ]

        response = client.chat.completions.create(
            #model="meta-llama-3.1-8b-instruct",
            #model='deepseek-r1-distill-llama-8b',
            model='gpt-4o-mini',
            messages=messages,
        )

        answer = response.choices[-1].message.content

        #print(answer)

        answers.append(answer)

        html = markdown.markdown(answer)

        # Parse HTML to extract list items
        soup = BeautifulSoup(html, 'html.parser')

        def parse_list(ul):
            items = []
            for li in ul.find_all('li', recursive=False):
                text = ''.join(li.find_all(string=True, recursive=False)).strip()
                sublist = li.find(['ul', 'ol'])
                if sublist:
                    items.append({text: parse_list(sublist)})
                else:
                    items.append(text)
            return items

        for ul in soup.find_all(['ul', 'ol'], recursive=False):
            l.extend(parse_list(ul))

    return l, answers

if __name__ == '__main__':
