Here is some other feedback I have from the PDF         │
│   process that we will start after you are completed      │
│   here and satisfied.: Direct PDF text extraction: Use a  │
│   fast local extractor (pdfminer/pymupdf) where license   │
│   allows, avoiding LLM for initial cleaning.              │
│   Single-pass per PDF: Ensure one cleaning/summarization  │
│   per unique PDF per run. ## Make sure you consider       │
│   your own approaches for fixing our PDF process. The     │
│   main idea here is whether or not we can just use a      │
│   dependency library to process it. We don't care about   │
│   what the output looks like at all. We just want to      │
│   capture the raw content. And if we don't get pictures   │
│   or images or whatever, none of that matters. We just    │
│   want to capture the raw context, the raw text content   │
│   of the PDF. Because if you remember, this is still in   │
│   the process of our pipeline where we feed the raw text  │
│   into an LLM for cleaning as well. So the PDF            │
│   processing of getting, extracting the text can be       │
│   pretty quick and dirty programmatically, hopefully,     │
│   rather than we don't want to have to rely on an LLM     │
│   for this step. Testing our approach out on the PDFs     │
│   that we just uncovered would be a good test to see if   │
│   it works. I know there are different types of PDFs so   │
│   the question is whether or not these are the type that  │
│   these libraries will work on.
