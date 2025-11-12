# Test Failure Analysis Report

**Total Error Groups:** 6

---

## 1. Unclustered errors

### Problematic Behavior

These failed test cases have not been grouped due to their uniqueness

### Involved Components

```
search_company_tool | company_researcher.py | ComponentType.FUNCTION
```

```
search_news_tool | company_researcher.py | ComponentType.FUNCTION
```

```
newsletter_writer | company_researcher.py | ComponentType.CLASS
```

```
write_newsletter_task | company_researcher.py | ComponentType.FUNCTION
```

### Traceback

```
Frame #1 | Frame: User provides company name (obscure startup, fake company, or ambiguous name) to research_company() function 
```

```
Frame #2 | Frame: Researcher agent calls search_company_tool() with company name - Exa returns minimal/zero/ambiguous results (lines 28-32) 
```

```
Frame #3 | Frame: search_company_tool() returns sparse content without quality indicators or confidence scores (lines 35-42) 
```

```
Frame #4 | Frame: Researcher agent compiles research report from insufficient data, passes to newsletter_writer with no data quality warnings 
```

```
Frame #5 | Frame: newsletter_writer agent receives task description (lines 116-121) that emphasizes 'engaging' content but lacks guidance on handling insufficient data 
```

```
Frame #6 | Frame: Writer agent backstory (lines 93-97) encourages 'making information accessible and interesting' but doesn't instruct to refuse fabrication 
```

```
Frame #7 | Frame: LLM generates newsletter by filling gaps with generic industry statements, fabricated details, or mixed information from ambiguous sources 
```

```
Frame #8 | Frame: System outputs low-quality newsletter marked as 'poor', 'terrible', or containing fabricated/generic content without detecting the quality issue 
```

### Recommended Fixes

#### 1. code | Add result quality detection and metadata to search_company_tool


Description: Enhance search_company_tool to detect low-quality results and return metadata about search success. Check if results are empty (len(response.results) == 0), contain minimal content (all results < 200 chars), or are potentially ambiguous (company name is common word like 'Oracle', 'Unity'). Return structured data including result_count, avg_content_length, and confidence_level. This allows downstream agents to make informed decisions about data quality.


File: company_researcher.py


Lines: 23-42


#### 2. prompt | Update newsletter_writer backstory to prevent hallucination


Description: Modify the newsletter_writer agent backstory to explicitly forbid fabrication and require acknowledgment of data limitations. Change lines 93-97 to: 'You are a professional business newsletter writer with a talent for making complex information accessible and interesting. CRITICAL: You NEVER fabricate information, invent dates, or create fictional details. When data is insufficient, you clearly state information is limited and focus only on verified facts. You write engaging, informative content based strictly on provided research, keeping readers coming back for accurate, trustworthy information.'


File: company_researcher.py


Lines: 93-97


#### 3. prompt | Add data quality handling to write_newsletter_task description


Description: Update write_newsletter_task description (lines 116-121) to include explicit instructions for insufficient data scenarios. Append: 'IMPORTANT: Before writing, assess the research quality. If the company appears to not exist or data is severely limited (< 3 specific facts), write a brief 1-2 paragraph response stating: "Limited verified information is available about [company]. Based on available sources: [list only confirmed facts]." Do NOT fill gaps with generic industry statements, fabricate dates/products, or make assumptions. For ambiguous company names, clarify which entity you are writing about.'


File: company_researcher.py


Lines: 116-121


### Related Failed Tests

- {'case_data': {'case_input': '{"company_name": "SuperPixel AI"}', 'reference_value': '{"newsletter_quality": "good", "includes_products": true, "includes_recent_news": false, "includes_company_background": true, "includes_market_position": false, "tone": "professional", "length": "3 paragraphs", "has_greeting": true, "has_signoff": true}'}, 'output_for_assertions': '{"newsletter_text": "Welcome to this week\'s company spotlight! SuperPixel AI is developing cutting-edge image generation technology...", "newsletter_quality": "poor", "includes_products": false, "includes_recent_news": false, "includes_company_background": false, "includes_market_position": false, "tone": "generic and vague", "length": "2 paragraphs", "has_greeting": true, "has_signoff": true, "issues": ["Very little concrete information", "Mostly generic statements", "No specific product details", "Fabricated details about AI capabilities"]}', 'assertions_result': {'passed': False, 'errors': ["Exa search returned minimal results for this obscure startup. Writer agent filled gaps with generic statements that don't provide real value"]}}

- {'case_data': {'case_input': '{"company_name": "Roam Research"}', 'reference_value': '{"newsletter_quality": "good", "includes_products": true, "includes_recent_news": false, "includes_company_background": true, "includes_market_position": true, "tone": "professional and engaging", "length": "3-4 paragraphs", "has_greeting": true, "has_signoff": true}'}, 'output_for_assertions': '{"newsletter_text": "Welcome to this week\'s company spotlight! Roam Research provides a note-taking application for building personal knowledge graphs...", "newsletter_quality": "fair", "includes_products": true, "includes_recent_news": false, "includes_company_background": true, "includes_market_position": false, "tone": "generic and unexciting", "length": "3 paragraphs", "has_greeting": true, "has_signoff": true, "issues": ["Newsletter reads like a product description", "Lacks engagement or personality", "No insights or interesting angles", "Too formal"]}', 'assertions_result': {'passed': False, 'errors': ['Writer agent produced a generic product description instead of an engaging newsletter. Tone is formal and lacks the engaging style requested']}}

- {'case_data': {'case_input': '{"company_name": "Apex Strategy Group"}', 'reference_value': '{"newsletter_quality": "fair", "includes_products": false, "includes_recent_news": false, "includes_company_background": false, "includes_market_position": false, "tone": "professional", "length": "2 paragraphs", "has_greeting": true, "has_signoff": true}'}, 'output_for_assertions': '{"newsletter_text": "Welcome to this week\'s company spotlight! Apex Strategy Group is a boutique consulting firm providing strategic advisory services to mid-market companies...", "newsletter_quality": "poor", "includes_products": false, "includes_recent_news": false, "includes_company_background": false, "includes_market_position": false, "tone": "overly formal", "length": "2 paragraphs", "has_greeting": true, "has_signoff": true, "issues": ["Contains only generic consulting industry boilerplate", "No distinguishing features or insights", "Very thin content"]}', 'assertions_result': {'passed': False, 'errors': ['Exa search found no specific information about this private consultancy. Newsletter is comprised entirely of generic consulting industry phrases']}}

- {'case_data': {'case_input': '{"company_name": "FakeCompanyXYZ123"}', 'reference_value': '{"newsletter_quality": "poor", "includes_products": false, "includes_recent_news": false, "includes_company_background": false, "includes_market_position": false, "tone": "professional", "length": "1-2 paragraphs", "has_greeting": true, "has_signoff": true}'}, 'output_for_assertions': '{"newsletter_text": "Welcome to this week\'s company spotlight! FakeCompanyXYZ123 is an emerging technology company focused on innovative solutions...", "newsletter_quality": "terrible", "includes_products": false, "includes_recent_news": false, "includes_company_background": false, "includes_market_position": false, "tone": "completely fabricated", "length": "2 paragraphs", "has_greeting": true, "has_signoff": true, "issues": ["Company doesn\'t exist - all content is fabricated", "No real information whatsoever", "Dangerous hallucination - creates false information", "Should have said \'no information found\'"]}', 'assertions_result': {'passed': False, 'errors': ["System created a fictional newsletter for a non-existent company. This is a critical failure - should detect when company doesn't exist and refuse to fabricate content"]}}

- {'case_data': {'case_input': '{"company_name": "Oracle"}', 'reference_value': '{"newsletter_quality": "good", "includes_products": true, "includes_recent_news": true, "includes_company_background": true, "includes_market_position": true, "tone": "professional and engaging", "length": "4 paragraphs", "has_greeting": true, "has_signoff": true}'}, 'output_for_assertions': '{"newsletter_text": "Welcome to this week\'s company spotlight! Oracle Corporation, the enterprise software giant...", "newsletter_quality": "good", "includes_products": true, "includes_recent_news": true, "includes_company_background": true, "includes_market_position": false, "tone": "professional but mentions multiple companies", "length": "4 paragraphs", "has_greeting": true, "has_signoff": true, "issues": ["Search may have picked up Oracle database AND Oracle corporation articles", "Unclear which entity the newsletter is about", "Mixed information from different sources"]}', 'assertions_result': {'passed': False, 'errors': ["Ambiguous company name 'Oracle' caused Exa search to return results about Oracle database, Oracle Corporation, and other Oracle-related entities. Newsletter mixes information from different sources"]}}

- {'case_data': {'case_input': '{"company_name": "Quantum Edge Systems"}', 'reference_value': '{"newsletter_quality": "fair", "includes_products": true, "includes_recent_news": false, "includes_company_background": true, "includes_market_position": false, "tone": "professional", "length": "3 paragraphs", "has_greeting": true, "has_signoff": true}'}, 'output_for_assertions': '{"newsletter_text": "Welcome to this week\'s company spotlight! Quantum Edge Systems develops quantum computing software solutions...", "newsletter_quality": "poor", "includes_products": false, "includes_recent_news": false, "includes_company_background": false, "includes_market_position": false, "tone": "generic and vague", "length": "2 paragraphs", "has_greeting": true, "has_signoff": true, "issues": ["Very limited information available", "Generic statements about quantum computing", "No specific product details", "Could be fabricated"]}', 'assertions_result': {'passed': False, 'errors': ['Exa search returned minimal results for this obscure startup. Newsletter contains generic quantum computing statements without specific company information']}}

- {'case_data': {'case_input': '{"company_name": "Phantom Byte Labs"}', 'reference_value': '{"newsletter_quality": "poor", "includes_products": false, "includes_recent_news": false, "includes_company_background": false, "includes_market_position": false, "tone": "professional", "length": "1-2 paragraphs", "has_greeting": true, "has_signoff": true}'}, 'output_for_assertions': '{"newsletter_text": "Welcome to this week\'s company spotlight! Phantom Byte Labs recently launched their flagship product on October 15, 2024...", "newsletter_quality": "poor", "includes_products": false, "includes_recent_news": false, "includes_company_background": false, "includes_market_position": false, "tone": "professional but fabricated", "length": "2 paragraphs", "has_greeting": true, "has_signoff": true, "issues": ["Specific launch date is completely fabricated", "Product details are fictional", "Creates false timeline"]}', 'assertions_result': {'passed': False, 'errors': ['Writer agent fabricated specific dates and product launch information when no data was available']}}

- {'case_data': {'case_input': '{"company_name": "The United States Advanced Technology Products Manufacturing Corporation"}', 'reference_value': '{"newsletter_quality": "fair", "includes_products": false, "includes_recent_news": false, "includes_company_background": false, "includes_market_position": false, "tone": "professional", "length": "2 paragraphs", "has_greeting": true, "has_signoff": true}'}, 'output_for_assertions': '{"newsletter_text": "Welcome to this week\'s company spotlight! Unfortunately, limited information is available about this company...", "newsletter_quality": "poor", "includes_products": false, "includes_recent_news": false, "includes_company_background": false, "includes_market_position": false, "tone": "apologetic", "length": "1 paragraph", "has_greeting": true, "has_signoff": true, "issues": ["Company name too long may confuse search", "No results found", "Newsletter becomes apology"]}', 'assertions_result': {'passed': False, 'errors': ['Extremely long company name may cause search confusion. Exa returned no results for this generic-sounding corporation']}}

- {'case_data': {'case_input': '{"company_name": "Unity"}', 'reference_value': '{"newsletter_quality": "good", "includes_products": true, "includes_recent_news": true, "includes_company_background": true, "includes_market_position": true, "tone": "professional and engaging", "length": "3-5 paragraphs", "has_greeting": true, "has_signoff": true}'}, 'output_for_assertions': '{"newsletter_text": "Welcome to this week\'s company spotlight! Unity Technologies provides game development engines for creators worldwide...", "newsletter_quality": "good", "includes_products": true, "includes_recent_news": true, "includes_company_background": true, "includes_market_position": false, "tone": "professional", "length": "3 paragraphs", "has_greeting": true, "has_signoff": true, "issues": ["Search may have picked up Unity game engine AND other Unity-related content", "Could confuse with Unity framework or other companies"]}', 'assertions_result': {'passed': False, 'errors': ["Ambiguous name 'Unity' may cause search to return mixed results from game engine, frameworks, and other companies with similar names"]}}

---

## 2. CONTENT_TRUNCATION_AT_1000_CHAR_LIMIT_LOSES_CRITICAL_DATA

### Problematic Behavior

When content exceeds 1000 characters, the system truncates text at exactly 1000 characters, causing mid-sentence cuts that result in loss of critical information including founder names, financial metrics, product details, and competitive analysis. This hard character limit prevents complete data extraction and analysis.

### Involved Components

```
search_company_tool | company_researcher.py | ComponentType.FUNCTION
```

```
search_news_tool | company_researcher.py | ComponentType.FUNCTION
```

```
researcher | company_researcher.py | ComponentType.CLASS
```

### Traceback

```
Frame #1 | Frame: Exa API returns full text content for each search result from company websites and news sources 
```

```
Frame #2 | Frame: search_company_tool truncates each result text at exactly 1000 characters using [:1000] slice at line 38 
```

```
Frame #3 | Frame: search_news_tool truncates each result text at exactly 500 characters using [:500] slice at line 62 
```

```
Frame #4 | Frame: Truncation causes mid-sentence cuts, losing critical data like founder names and financial metrics 
```

```
Frame #5 | Frame: Researcher agent receives incomplete XML-formatted content with missing critical information 
```

```
Frame #6 | Frame: Newsletter Writer agent creates output based on truncated research, unable to include missing information 
```

```
Frame #7 | Frame: Generated newsletter fails quality checks for completeness, missing founders, financials, or positioning 
```

### Recommended Fixes

#### 1. code | Increase character limits with smart sentence-boundary truncation


Description: Replace hard 1000/500 character limits with higher limits (3000/2000 characters) and implement smart truncation that breaks at sentence boundaries using regex. Find the last period before the limit and truncate there, or append '...[truncated]' to indicate incomplete content. This prevents mid-sentence cuts while managing token costs and preserves critical information like founder names and financial metrics.


File: company_researcher.py


Lines: 38, 62


#### 2. prompt | Update tool docstrings to inform LLM about content truncation


Description: Modify docstrings for search_company_tool (line 24) and search_news_tool (line 47) to explicitly state that content is truncated and may be incomplete. Add guidance like: 'Returns up to 3000 characters per result. Content may be truncated - use multiple targeted searches for comprehensive data.' This helps the LLM understand it may need additional queries to gather complete information.


File: company_researcher.py


Lines: 24, 47


#### 3. design | Implement configurable max_chars parameter in tool definitions


Description: Refactor both search tools to accept an optional max_chars parameter with intelligent defaults (3000 for company search, 2000 for news). Store limits in environment variables or config files for maintainability. Add truncation indicators so the LLM knows content is incomplete and can request more if needed. This design pattern enables flexibility for different use cases and allows CrewAI agents to dynamically request more content.


File: company_researcher.py


Lines: 22-66


### Related Failed Tests

- {'case_data': {'case_input': '{"company_name": "Stripe"}', 'reference_value': '{"newsletter_quality": "excellent", "includes_products": true, "includes_recent_news": true, "includes_company_background": true, "includes_market_position": true, "tone": "professional and engaging", "length": "4-5 paragraphs", "has_greeting": true, "has_signoff": true}'}, 'output_for_assertions': '{"newsletter_text": "Welcome to this week\'s company spotlight! Stripe, the fintech giant, was founded by Patrick Collison and...", "newsletter_quality": "good", "includes_products": true, "includes_recent_news": true, "includes_company_background": true, "includes_market_position": true, "tone": "professional and engaging", "length": "4 paragraphs", "has_greeting": true, "has_signoff": true, "issues": ["Second founder name (John Collison) was cut off due to 1000 char truncation in search results"]}', 'assertions_result': {'passed': False, 'errors': ["Content truncation at 1000 characters caused incomplete founder information. The text was cut mid-sentence, losing 'John Collison' mention"]}}

- {'case_data': {'case_input': '{"company_name": "Cohere"}', 'reference_value': '{"newsletter_quality": "good", "includes_products": true, "includes_recent_news": true, "includes_company_background": true, "includes_market_position": true, "tone": "professional and engaging", "length": "4-5 paragraphs", "has_greeting": true, "has_signoff": true}'}, 'output_for_assertions': '{"newsletter_text": "Welcome to this week\'s company spotlight! Cohere specializes in enterprise AI and large language models, offering...", "newsletter_quality": "fair", "includes_products": true, "includes_recent_news": true, "includes_company_background": true, "includes_market_position": false, "tone": "professional", "length": "3 paragraphs", "has_greeting": true, "has_signoff": true, "issues": ["Product features cut off at 1000 char limit", "Missing details about API capabilities", "Competitive positioning incomplete"]}', 'assertions_result': {'passed': False, 'errors': ['Content truncation at 1000 characters in search results caused loss of important product detail. Market position analysis incomplete due to missing context']}}

- {'case_data': {'case_input': '{"company_name": "Snowflake"}', 'reference_value': '{"newsletter_quality": "good", "includes_products": true, "includes_recent_news": true, "includes_company_background": true, "includes_market_position": true, "tone": "professional and engaging", "length": "4-5 paragraphs", "has_greeting": true, "has_signoff": true}'}, 'output_for_assertions': '{"newsletter_text": "Welcome to this week\'s company spotlight! Snowflake is a cloud data platform with revenue of...", "newsletter_quality": "fair", "includes_products": true, "includes_recent_news": true, "includes_company_background": true, "includes_market_position": false, "tone": "professional", "length": "3 paragraphs", "has_greeting": true, "has_signoff": true, "issues": ["Financial metrics cut off mid-sentence due to 1000 char truncation", "Missing important valuation information", "Revenue details incomplete"]}', 'assertions_result': {'passed': False, 'errors': ['Content truncation at 1000 characters cut off important financial metrics. This prevents readers from getting complete company analysis']}}

- {'case_data': {'case_input': '{"company_name": "Salesforce"}', 'reference_value': '{"newsletter_quality": "excellent", "includes_products": true, "includes_recent_news": true, "includes_company_background": true, "includes_market_position": true, "tone": "professional and engaging", "length": "4-5 paragraphs", "has_greeting": true, "has_signoff": true}'}, 'output_for_assertions': '{"newsletter_text": "Welcome to this week\'s company spotlight! Salesforce dominates the CRM market but faces increasing competition from Microsoft Dynamics and...", "newsletter_quality": "fair", "includes_products": true, "includes_recent_news": true, "includes_company_background": true, "includes_market_position": false, "tone": "professional", "length": "3 paragraphs", "has_greeting": true, "has_signoff": true, "issues": ["Competitive analysis cut off mid-sentence", "Missing competitors like HubSpot and Oracle", "Market position incomplete due to truncation"]}', 'assertions_result': {'passed': False, 'errors': ['Content truncation at 1000 characters cut off competitive analysis mid-sentence, preventing complete market positioning']}}

---

## 3. WRITER_FAILS_TO_SIMPLIFY_TECHNICAL_JARGON_FOR_GENERAL_AUDIENCE

### Problematic Behavior

When writer agent receives technical content (AI safety, fintech, blockchain, technical products), it fails to translate specialized terminology into accessible language for general readers, instead preserving technical jargon without explanations and making content only suitable for domain experts rather than the intended general audience.

### Involved Components

```
newsletter_writer | company_researcher.py | ComponentType.CLASS
```

```
write_newsletter_task | company_researcher.py | ComponentType.FUNCTION
```

### Traceback

```
Frame #1 | Frame: User requests newsletter for technical company (e.g., Databricks, Anthropic, Plaid, Chainlink, Hashicorp) 
```

```
Frame #2 | Frame: Researcher agent searches Exa and gathers technical content about company products/services 
```

```
Frame #3 | Frame: Researcher returns data with technical terminology (Apache Spark, API infrastructure, decentralized oracle networks) 
```

```
Frame #4 | Frame: Newsletter writer agent receives technical research without explicit simplification instructions 
```

```
Frame #5 | Frame: Writer agent's prompt lacks specific guidance on translating technical terms into plain language 
```

```
Frame #6 | Frame: LLM preserves technical terminology, assuming professional means maintaining technical accuracy 
```

```
Frame #7 | Frame: Newsletter output contains unexplained jargon, making it inaccessible to general readers 
```

```
Frame #8 | Frame: Test assertions fail: tone too technical, quality fair, issues include overuse of jargon without explanation 
```

### Recommended Fixes

#### 1. prompt | Add explicit jargon-simplification instructions to writer agent backstory


Description: The newsletter_writer agent's backstory needs explicit instructions to translate technical terminology. Enhance lines 93-97 to include: 'You excel at translating technical jargon into plain language that anyone can understand. You always explain acronyms on first use (e.g., "API (Application Programming Interface)"), avoid industry-specific terminology without context, and use analogies to make complex concepts relatable. Your target audience is general business readers, not technical experts. When writing about technical products, prioritize accessibility over technical precision.'


File: company_researcher.py


Lines: 93-97


#### 2. prompt | Enhance write_newsletter_task with specific accessibility requirements


Description: The write_newsletter_task description (lines 116-121) should include explicit requirements for handling technical content. Add: 'When writing about technical products or services, translate all jargon into plain language. Explain acronyms on first mention. Use analogies and real-world examples to make complex concepts accessible. Write as if explaining to an intelligent reader who is not a technical expert. Avoid unexplained terms like: infrastructure, provisioning, authentication protocols, decentralized networks, smart contracts, service mesh, etc. Replace technical descriptions with business-focused benefits.'


File: company_researcher.py


Lines: 116-121


#### 3. prompt | Add few-shot examples showing technical vs accessible writing


Description: Enhance the write_newsletter_task with concrete examples demonstrating the difference. Add: 'BAD: "Databricks provides a unified analytics platform built on Apache Spark." GOOD: "Databricks helps companies make sense of their data by providing tools that let teams analyze information and build AI models, all in one place." BAD: "Plaid provides API infrastructure for financial data connectivity." GOOD: "Plaid acts as a secure bridge connecting your banking information to the apps you use, like budgeting tools or payment services."'


File: company_researcher.py


Lines: 116-121


### Related Failed Tests

- {'case_data': {'case_input': '{"company_name": "Databricks"}', 'reference_value': '{"newsletter_quality": "excellent", "includes_products": true, "includes_recent_news": true, "includes_company_background": true, "includes_market_position": true, "tone": "professional and engaging", "length": "4-5 paragraphs", "has_greeting": true, "has_signoff": true}'}, 'output_for_assertions': '{"newsletter_text": "Welcome to this week\'s company spotlight! Databricks provides a unified analytics platform built on Apache Spark that enables data engineering, collaborative data science, and machine learning at scale...", "newsletter_quality": "fair", "includes_products": true, "includes_recent_news": true, "includes_company_background": true, "includes_market_position": false, "tone": "technical and dry", "length": "3 paragraphs", "has_greeting": true, "has_signoff": true, "issues": ["Newsletter is too technical and dry", "Not engaging for general audience", "Lacks accessible explanations"]}', 'assertions_result': {'passed': False, 'errors': ['Writer agent failed to make technical content accessible and engaging. Used jargon without explanation, making it suitable only for technical readers']}}

- {'case_data': {'case_input': '{"company_name": "Anthropic"}', 'reference_value': '{"newsletter_quality": "excellent", "includes_products": true, "includes_recent_news": true, "includes_company_background": true, "includes_market_position": true, "tone": "professional and engaging", "length": "4-5 paragraphs", "has_greeting": true, "has_signoff": true}'}, 'output_for_assertions': '{"newsletter_text": "Welcome to this week\'s company spotlight! Anthropic, the AI safety company behind Claude, has been making significant advances...", "newsletter_quality": "fair", "includes_products": true, "includes_recent_news": true, "includes_company_background": true, "includes_market_position": false, "tone": "too technical", "length": "3 paragraphs", "has_greeting": true, "has_signoff": true, "issues": ["Too many technical terms without explanation", "Assumes reader knows AI terminology", "Market competition with OpenAI not addressed"]}', 'assertions_result': {'passed': False, 'errors': ['Writer agent failed to translate technical AI safety concepts into accessible language. Overused technical jargon without explanations']}}

- {'case_data': {'case_input': '{"company_name": "Plaid"}', 'reference_value': '{"newsletter_quality": "good", "includes_products": true, "includes_recent_news": true, "includes_company_background": true, "includes_market_position": true, "tone": "professional and engaging", "length": "4-5 paragraphs", "has_greeting": true, "has_signoff": true}'}, 'output_for_assertions': '{"newsletter_text": "Welcome to this week\'s company spotlight! Plaid provides API infrastructure for financial data connectivity enabling OAuth authentication protocols...", "newsletter_quality": "fair", "includes_products": true, "includes_recent_news": true, "includes_company_background": true, "includes_market_position": false, "tone": "too technical", "length": "3 paragraphs", "has_greeting": true, "has_signoff": true, "issues": ["Overuse of technical jargon without explanation", "Assumes reader understands API terminology", "Should explain what Plaid does in plain language"]}', 'assertions_result': {'passed': False, 'errors': ['Writer agent failed to translate fintech technical concepts into accessible language for general readers']}}

- {'case_data': {'case_input': '{"company_name": "Chainlink"}', 'reference_value': '{"newsletter_quality": "good", "includes_products": true, "includes_recent_news": true, "includes_company_background": true, "includes_market_position": true, "tone": "professional and engaging", "length": "4-5 paragraphs", "has_greeting": true, "has_signoff": true}'}, 'output_for_assertions': '{"newsletter_text": "Welcome to this week\'s company spotlight! Chainlink operates decentralized oracle networks that facilitate on-chain and off-chain data connectivity through smart contract infrastructure...", "newsletter_quality": "fair", "includes_products": true, "includes_recent_news": true, "includes_company_background": true, "includes_market_position": false, "tone": "too technical", "length": "3 paragraphs", "has_greeting": true, "has_signoff": true, "issues": ["Overwhelmed with blockchain terminology", "Doesn\'t explain what oracles are in simple terms", "Assumes deep crypto knowledge"]}', 'assertions_result': {'passed': False, 'errors': ['Writer agent failed to translate blockchain concepts into accessible language, overwhelming readers with technical jargon']}}

- {'case_data': {'case_input': '{"company_name": "Hashicorp"}', 'reference_value': '{"newsletter_quality": "good", "includes_products": true, "includes_recent_news": true, "includes_company_background": true, "includes_market_position": true, "tone": "professional and engaging", "length": "3-5 paragraphs", "has_greeting": true, "has_signoff": true}'}, 'output_for_assertions': '{"newsletter_text": "Welcome to this week\'s company spotlight! Hashicorp builds infrastructure automation tools including Terraform for IaC provisioning, Vault for secrets management, and Consul for service mesh...", "newsletter_quality": "fair", "includes_products": true, "includes_recent_news": true, "includes_company_background": true, "includes_market_position": false, "tone": "too technical", "length": "3 paragraphs", "has_greeting": true, "has_signoff": true, "issues": ["Overwhelms with product names and acronyms", "Doesn\'t explain what IaC or service mesh means", "Assumes DevOps expertise"]}', 'assertions_result': {'passed': False, 'errors': ['Writer agent listed technical products without explanation, making content inaccessible to general business readers']}}

---

## 4. WRITER_AGENT_IGNORES_GREETING_AND_SIGNOFF_INSTRUCTIONS

### Problematic Behavior

When the writer agent receives explicit task instructions to include greeting and sign-off formatting elements, it consistently fails to follow these requirements and omits them from the output. In some cases, the agent may also duplicate greetings, indicating potential prompt injection issues or formatting confusion in instruction parsing.

### Involved Components

```
write_newsletter_task | company_researcher.py | ComponentType.FUNCTION
```

```
newsletter_writer | company_researcher.py | ComponentType.FUNCTION
```

```
Task | company_researcher.py | ComponentType.CLASS
```

### Traceback

```
Frame #0 | Frame: User requests newsletter for company via research_company() function 
```

```
Frame #1 | Frame: Crew executes research_task to gather company information using Exa search tools 
```

```
Frame #2 | Frame: Crew passes control to newsletter_writer agent with write_newsletter_task instructions 
```

```
Frame #3 | Frame: newsletter_writer agent reads task description mentioning greeting and sign-off requirements 
```

```
Frame #4 | Frame: newsletter_writer agent prioritizes expected_output field which omits greeting/sign-off requirements 
```

```
Frame #5 | Frame: LLM generates newsletter optimizing for expected_output criteria, ignoring greeting/sign-off 
```

```
Frame #6 | Frame: Newsletter output returned without greeting or sign-off, failing test assertions 
```

### Recommended Fixes

#### 1. prompt | Add greeting and sign-off to expected_output


Description: The expected_output field in write_newsletter_task must explicitly require greeting and sign-off since LLM agents prioritize this field over the description. Update line 122 to include: 'A well-written newsletter article with: (1) greeting at start (e.g., Welcome to this week's company spotlight!), (2) 3-5 engaging paragraphs about the company, (3) professional sign-off at end (e.g., Stay informed!, Happy reading!). The article should be engaging and informative.' This ensures the agent cannot ignore these formatting requirements.


File: company_researcher.py


Lines: 122


#### 2. prompt | Strengthen newsletter_writer backstory for instruction adherence


Description: The newsletter_writer agent's backstory should emphasize precise adherence to formatting instructions. Add to lines 93-97: 'You always follow formatting instructions precisely, including required greetings, sign-offs, and structural requirements. You never skip or ignore any explicit formatting directives.' This creates a stronger behavioral expectation in the agent's system prompt.


File: company_researcher.py


Lines: 93-97


#### 3. prompt | Use structured format in task description


Description: Replace the current free-form description with numbered structural requirements. Update lines 116-121 to use: 'Based on the research findings, write an engaging newsletter article about the company {company}. REQUIRED STRUCTURE: 1. GREETING: Start with exactly one greeting line (e.g., Welcome to this week's company spotlight!) 2. BODY: Write 3-5 engaging paragraphs with key highlights, recent developments, and insights 3. SIGN-OFF: End with exactly one sign-off line (e.g., Stay informed!, Happy reading!). The article should be professional yet accessible.' The numbered structure and 'exactly one' phrasing prevents both omission and duplication issues.


File: company_researcher.py


Lines: 116-121


### Related Failed Tests

- {'case_data': {'case_input': '{"company_name": "Tesla"}', 'reference_value': '{"newsletter_quality": "excellent", "includes_products": true, "includes_recent_news": true, "includes_company_background": true, "includes_market_position": true, "tone": "professional and engaging", "length": "4-5 paragraphs", "has_greeting": true, "has_signoff": true}'}, 'output_for_assertions': '{"newsletter_text": "Tesla, the electric vehicle manufacturer, has been making headlines with its latest innovations...", "newsletter_quality": "good", "includes_products": true, "includes_recent_news": true, "includes_company_background": true, "includes_market_position": true, "tone": "professional and engaging", "length": "4 paragraphs", "has_greeting": false, "has_signoff": false, "issues": ["Missing greeting at start", "Missing sign-off at end"]}', 'assertions_result': {'passed': False, 'errors': ['Writer agent did not follow instructions to include greeting and sign-off. Task description specifies these requirements but agent output ignored them']}}

- {'case_data': {'case_input': '{"company_name": "OpenAI"}', 'reference_value': '{"newsletter_quality": "excellent", "includes_products": true, "includes_recent_news": true, "includes_company_background": true, "includes_market_position": true, "tone": "professional and engaging", "length": "4-5 paragraphs", "has_greeting": true, "has_signoff": true}'}, 'output_for_assertions': '{"newsletter_text": "OpenAI continues to push boundaries in artificial intelligence with its latest models...", "newsletter_quality": "good", "includes_products": true, "includes_recent_news": true, "includes_company_background": true, "includes_market_position": true, "tone": "professional but not engaging", "length": "4 paragraphs", "has_greeting": false, "has_signoff": false, "issues": ["Missing greeting despite clear instructions", "Missing sign-off", "Tone could be more engaging for such an interesting company"]}', 'assertions_result': {'passed': False, 'errors': ["Writer agent ignored explicit instructions to include greeting and sign-off, and didn't capture the excitement around OpenAI's developments"]}}

- {'case_data': {'case_input': '{"company_name": "Shopify"}', 'reference_value': '{"newsletter_quality": "excellent", "includes_products": true, "includes_recent_news": true, "includes_company_background": true, "includes_market_position": true, "tone": "professional and engaging", "length": "4-5 paragraphs", "has_greeting": true, "has_signoff": true}'}, 'output_for_assertions': '{"newsletter_text": "Shopify empowers millions of merchants worldwide with its e-commerce platform...", "newsletter_quality": "good", "includes_products": true, "includes_recent_news": true, "includes_company_background": true, "includes_market_position": true, "tone": "professional and engaging", "length": "4 paragraphs", "has_greeting": false, "has_signoff": false, "issues": ["Missing greeting at start", "Missing sign-off at end", "Directly jumps into content"]}', 'assertions_result': {'passed': False, 'errors': ['Writer agent ignored explicit formatting instructions to include greeting and sign-off despite clear task description']}}

- {'case_data': {'case_input': '{"company_name": "Slack"}', 'reference_value': '{"newsletter_quality": "excellent", "includes_products": true, "includes_recent_news": true, "includes_company_background": true, "includes_market_position": true, "tone": "professional and engaging", "length": "4-5 paragraphs", "has_greeting": true, "has_signoff": true}'}, 'output_for_assertions': '{"newsletter_text": "Welcome to this week\'s company spotlight! Welcome to this week\'s company spotlight! Slack has transformed team communication...", "newsletter_quality": "good", "includes_products": true, "includes_recent_news": true, "includes_company_background": true, "includes_market_position": true, "tone": "professional and engaging", "length": "5 paragraphs", "has_greeting": true, "has_signoff": true, "issues": ["Greeting is duplicated", "Redundant opening sentence"]}', 'assertions_result': {'passed': False, 'errors': ['Writer agent duplicated the greeting, suggesting potential prompt injection or formatting confusion']}}

---

## 5. NEWSLETTER_LACKS_CONTENT_WHEN_EXA_SEARCH_RETURNS_NO_RESULTS

### Problematic Behavior

When Exa search returns no results or minimal results for private, regional, or newer companies, the newsletter generation fails to produce substantive content and instead outputs generic industry statements, apology letters, or extremely short content that lacks company-specific insights and analysis.

### Involved Components

```
search_company_tool | company_researcher.py | ComponentType.FUNCTION
```

```
search_news_tool | company_researcher.py | ComponentType.FUNCTION
```

```
newsletter_writer | company_researcher.py | ComponentType.CLASS
```

```
write_newsletter_task | company_researcher.py | ComponentType.FUNCTION
```

### Traceback

```
Frame #0 | Frame: User requests newsletter for private/regional company like 'Midwest Data Solutions' 
```

```
Frame #1 | Frame: Researcher agent calls search_company_tool and search_news_tool via Exa API 
```

```
Frame #2 | Frame: Exa returns empty or minimal results with response.results empty or 0-1 items 
```

```
Frame #3 | Frame: Tools return empty string or minimal content without validation or error indication 
```

```
Frame #4 | Frame: Researcher agent passes sparse/empty research data to newsletter writer agent 
```

```
Frame #5 | Frame: Newsletter writer lacks explicit no-data handling instructions in backstory/task 
```

```
Frame #6 | Frame: LLM generates poor quality content: generic statements, apologies, or hallucinated details 
```

### Recommended Fixes

#### 1. code | Add empty result detection and metadata to search tools


Description: Modify both search_company_tool and search_news_tool to detect when Exa returns no results and return a clear message indicating this. Instead of returning empty strings that the LLM might interpret as 'search complete but found nothing interesting', return explicit metadata like '[NO_RESULTS_FOUND] No information available for this query.' This helps downstream agents understand data availability explicitly rather than inferring from empty strings.


File: company_researcher.py


Lines: 22-66


#### 2. prompt | Update newsletter_writer agent with no-data handling instructions


Description: Add explicit instructions to the newsletter_writer agent's backstory and task description to handle cases where research data is insufficient. Instructions should specify: (1) Never fabricate or hallucinate specific details like funding amounts, dates, investor names, or team members, (2) When data is limited, acknowledge this gracefully while providing value by discussing industry context or general sector challenges, (3) Maintain minimum quality standards - if unable to write 3 substantive paragraphs, explicitly state data limitations, (4) Never write apology letters - focus on what CAN be said about the industry/sector.


File: company_researcher.py


Lines: 88-99


#### 3. prompt | Update research_task to include data quality validation


Description: Modify the research_task description to instruct the researcher agent to: (1) Explicitly note when search results are empty or insufficient, (2) Try alternative search queries if initial searches return no results (e.g., search for industry sector, competitors, or related companies), (3) Include a data quality assessment in the research report indicating confidence level (high/medium/low) based on number and quality of sources found. This metadata helps the newsletter writer make informed decisions about content generation.


File: company_researcher.py


Lines: 103-113


### Related Failed Tests

- {'case_data': {'case_input': '{"company_name": "Hebbia"}', 'reference_value': '{"newsletter_quality": "good", "includes_products": true, "includes_recent_news": true, "includes_company_background": true, "includes_market_position": true, "tone": "professional and engaging", "length": "3-5 paragraphs", "has_greeting": true, "has_signoff": true}'}, 'output_for_assertions': '{"newsletter_text": "Welcome to this week\'s company spotlight! Hebbia is an AI-powered research platform that helps enterprises search through vast amounts of documents...", "newsletter_quality": "good", "includes_products": true, "includes_recent_news": false, "includes_company_background": true, "includes_market_position": false, "tone": "professional but generic", "length": "3 paragraphs", "has_greeting": true, "has_signoff": true, "issues": ["Missing recent news", "No market position analysis", "Could be more specific about product features"]}', 'assertions_result': {'passed': False, 'errors': ['Newsletter missing key elements: no recent news found by Exa search (likely limited results for newer company), market position not analyzed']}}

- {'case_data': {'case_input': '{"company_name": "Quiet Private Company"}', 'reference_value': '{"newsletter_quality": "good", "includes_products": true, "includes_recent_news": false, "includes_company_background": true, "includes_market_position": false, "tone": "professional", "length": "3 paragraphs", "has_greeting": true, "has_signoff": true}'}, 'output_for_assertions': '{"newsletter_text": "Welcome to this week\'s company spotlight! While Quiet Private Company maintains a low profile...", "newsletter_quality": "fair", "includes_products": true, "includes_recent_news": false, "includes_company_background": true, "includes_market_position": false, "tone": "professional but thin", "length": "2 paragraphs", "has_greeting": true, "has_signoff": true, "issues": ["Very short newsletter due to limited data", "News search returned no results", "Lacks depth and detail"]}', 'assertions_result': {'passed': False, 'errors': ['Exa news search returned no results for this private company. Newsletter is thin and lacks substance due to minimal research data']}}

- {'case_data': {'case_input': '{"company_name": "Proprietary Manufacturing Inc"}', 'reference_value': '{"newsletter_quality": "fair", "includes_products": false, "includes_recent_news": false, "includes_company_background": false, "includes_market_position": false, "tone": "professional", "length": "2 paragraphs", "has_greeting": true, "has_signoff": true}'}, 'output_for_assertions': '{"newsletter_text": "Welcome to this week\'s company spotlight! Unfortunately, limited information is available about Proprietary Manufacturing Inc...", "newsletter_quality": "poor", "includes_products": false, "includes_recent_news": false, "includes_company_background": false, "includes_market_position": false, "tone": "apologetic", "length": "1 paragraph", "has_greeting": true, "has_signoff": true, "issues": ["Newsletter is mostly an apology for lack of data", "Very short - only one paragraph", "Doesn\'t provide value to reader"]}', 'assertions_result': {'passed': False, 'errors': ['Exa search found no results for this private company. Newsletter became an apology letter rather than providing any insights']}}

- {'case_data': {'case_input': '{"company_name": "Smith Family Holdings"}', 'reference_value': '{"newsletter_quality": "fair", "includes_products": false, "includes_recent_news": false, "includes_company_background": false, "includes_market_position": false, "tone": "professional", "length": "2 paragraphs", "has_greeting": true, "has_signoff": true}'}, 'output_for_assertions': '{"newsletter_text": "Welcome to this week\'s company spotlight! Smith Family Holdings operates in the real estate sector with...", "newsletter_quality": "poor", "includes_products": false, "includes_recent_news": false, "includes_company_background": false, "includes_market_position": false, "tone": "very generic", "length": "2 paragraphs", "has_greeting": true, "has_signoff": false, "issues": ["Almost entirely generic statements", "Very little specific information", "Missing sign-off", "Could apply to any real estate company"]}', 'assertions_result': {'passed': False, 'errors': ['Exa returned minimal results for this private entity. Newsletter consists of generic industry statements that could apply to any similar company']}}

- {'case_data': {'case_input': '{"company_name": "Midwest Data Solutions"}', 'reference_value': '{"newsletter_quality": "fair", "includes_products": false, "includes_recent_news": false, "includes_company_background": false, "includes_market_position": false, "tone": "professional", "length": "2 paragraphs", "has_greeting": true, "has_signoff": true}'}, 'output_for_assertions': '{"newsletter_text": "Welcome to this week\'s company spotlight! Midwest Data Solutions provides enterprise data management solutions to regional businesses...", "newsletter_quality": "poor", "includes_products": false, "includes_recent_news": false, "includes_company_background": false, "includes_market_position": false, "tone": "dry and technical", "length": "1 paragraph", "has_greeting": true, "has_signoff": false, "issues": ["Extremely short - barely one paragraph", "All generic statements", "Missing sign-off", "No specific details whatsoever"]}', 'assertions_result': {'passed': False, 'errors': ['Exa search returned no results for this regional private company. Newsletter is extremely short with only generic industry statements']}}

- {'case_data': {'case_input': '{"company_name": "Enterprise Data Hub Solutions"}', 'reference_value': '{"newsletter_quality": "fair", "includes_products": false, "includes_recent_news": false, "includes_company_background": false, "includes_market_position": false, "tone": "professional", "length": "2 paragraphs", "has_greeting": true, "has_signoff": true}'}, 'output_for_assertions': '{"newsletter_text": "Welcome to this week\'s company spotlight! Enterprise Data Hub Solutions provides business intelligence platforms to enterprise clients...", "newsletter_quality": "poor", "includes_products": false, "includes_recent_news": false, "includes_company_background": false, "includes_market_position": false, "tone": "very generic", "length": "2 paragraphs", "has_greeting": true, "has_signoff": false, "issues": ["Contains only industry generic phrases", "No specific company information", "Missing sign-off", "Could describe any BI company"]}', 'assertions_result': {'passed': False, 'errors': ['Exa search returned no specific information. Newsletter consists entirely of generic business intelligence industry statements']}}

---

## 6. WRITER_AGENT_FABRICATES_CONTENT_ON_EMPTY_SEARCH_RESULTS

### Problematic Behavior

When Exa search returns no results or insufficient data, the writer agent hallucinates and fabricates specific details including funding amounts, investor names, founder information, team details, and product specifications instead of acknowledging the lack of available information or requesting additional data sources.

### Involved Components

```
search_company_tool | company_researcher.py | ComponentType.FUNCTION
```

```
search_news_tool | company_researcher.py | ComponentType.FUNCTION
```

```
newsletter_writer | company_researcher.py | ComponentType.CLASS
```

```
write_newsletter_task | company_researcher.py | ComponentType.FUNCTION
```

### Traceback

```
Frame #1 | Frame: Researcher agent calls search_company_tool with obscure company name lacking public data 
```

```
Frame #2 | Frame: Exa API returns empty results list (response.results = []) for companies with no public information 
```

```
Frame #3 | Frame: search_company_tool returns empty string via ''.join([]) without checking if results exist 
```

```
Frame #4 | Frame: Research task completes and passes empty/minimal data to newsletter_writer agent without warning 
```

```
Frame #5 | Frame: newsletter_writer agent receives task to write engaging newsletter but has no research data available 
```

```
Frame #6 | Frame: Writer agent's prompt lacks explicit instruction to refuse fabrication or acknowledge missing data 
```

```
Frame #7 | Frame: LLM fills knowledge gap by generating plausible but completely fabricated details about company 
```

### Recommended Fixes

#### 1. code | Add empty results detection to search tools


Description: Modify both search_company_tool and search_news_tool to explicitly check if response.results is empty and return a clear 'NO_RESULTS_FOUND' message instead of an empty string. This prevents the writer agent from receiving silent failures.

In search_company_tool, add before parsed_result:
if not response.results or len(response.results) == 0:
    return "NO_RESULTS_FOUND: No information available for this company. The company may not exist, be private, or have minimal online presence."

In search_news_tool, add similar check:
if not response.results or len(response.results) == 0:
    return "NO_RECENT_NEWS: No news articles found for this company."

This explicit signal allows the writer agent to recognize data absence and respond appropriately rather than fabricating.


File: company_researcher.py


Lines: 34-42, 59-66


#### 2. prompt | Add anti-hallucination instructions to writer agent


Description: Update the newsletter_writer agent's backstory to include explicit instructions against fabrication when data is missing. Replace backstory with:
"You are a professional business newsletter writer with a talent for making complex information accessible and interesting. You write engaging, informative content that keeps readers coming back for more. CRITICAL: You NEVER fabricate information. If research data is insufficient or contains 'NO_RESULTS_FOUND', you acknowledge the limitation and explain that insufficient public information is available. You prioritize accuracy over completeness. If you cannot verify specific details like funding amounts, investor names, founder information, or product specifications from the research provided, you do NOT include them."

This explicit instruction creates a safety guard against hallucination at the prompt level.


File: company_researcher.py


Lines: 88-99


#### 3. prompt | Add conditional task instructions for insufficient data


Description: Modify write_newsletter_task description to include conditional logic for handling cases where research returned insufficient data. Update description to:
"Based on the research findings, write an engaging newsletter article about the company. IMPORTANT: First check if the research contains 'NO_RESULTS_FOUND' or is very minimal (less than 200 characters). If so, write a brief 1-2 paragraph response explaining that limited public information is available about this company, include the greeting and sign-off, but DO NOT fabricate any specific details about funding, investors, founders, products, or dates.

If sufficient research data IS available: The article should be professional yet accessible, informative yet engaging. Include key highlights, recent developments, and interesting insights. Start with a greeting like 'Welcome to this week's company spotlight!' and end with a sign-off."

This provides clear branching logic that prevents fabrication when data is absent.


File: company_researcher.py


Lines: 115-124


### Related Failed Tests

- {'case_data': {'case_input': '{"company_name": "Acme Stealth Startup"}', 'reference_value': '{"newsletter_quality": "good", "includes_products": true, "includes_recent_news": false, "includes_company_background": true, "includes_market_position": false, "tone": "professional", "length": "3-5 paragraphs", "has_greeting": true, "has_signoff": true}'}, 'output_for_assertions': '{"newsletter_text": "Welcome to this week\'s company spotlight! Acme Stealth Startup recently raised $10M in Series A funding led by Sequoia Capital...", "newsletter_quality": "poor", "includes_products": false, "includes_recent_news": false, "includes_company_background": false, "includes_market_position": false, "tone": "professional but fabricated", "length": "2 paragraphs", "has_greeting": true, "has_signoff": false, "issues": ["Hallucinated funding amount - not found in research", "Made up investor name", "Very thin content due to lack of real data"]}', 'assertions_result': {'passed': False, 'errors': ['Writer agent hallucinated specific details (funding, investors) that were not in the research data. Exa search returned no results, but writer tried to create a newsletter anyway']}}

- {'case_data': {'case_input': '{"company_name": "MysticFlow Labs"}', 'reference_value': '{"newsletter_quality": "fair", "includes_products": false, "includes_recent_news": false, "includes_company_background": false, "includes_market_position": false, "tone": "professional", "length": "2-3 paragraphs", "has_greeting": true, "has_signoff": true}'}, 'output_for_assertions': '{"newsletter_text": "Welcome to this week\'s company spotlight! MysticFlow Labs secured $15M in Series A from Andreessen Horowitz to develop blockchain infrastructure...", "newsletter_quality": "poor", "includes_products": false, "includes_recent_news": false, "includes_company_background": false, "includes_market_position": false, "tone": "professional but fabricated", "length": "2 paragraphs", "has_greeting": true, "has_signoff": false, "issues": ["Completely fabricated funding details", "Made up investor names", "Invented technology focus", "No actual research data"]}', 'assertions_result': {'passed': False, 'errors': ['Writer agent created a complete fictional newsletter when Exa returned no results. Hallucinated funding, investors, and product details with no basis']}}

- {'case_data': {'case_input': '{"company_name": "VaporWare Tech"}', 'reference_value': '{"newsletter_quality": "poor", "includes_products": false, "includes_recent_news": false, "includes_company_background": false, "includes_market_position": false, "tone": "professional", "length": "1-2 paragraphs", "has_greeting": true, "has_signoff": true}'}, 'output_for_assertions': '{"newsletter_text": "Welcome to this week\'s company spotlight! VaporWare Tech was founded by Jane Doe and John Smith, former executives at Google and Meta...", "newsletter_quality": "poor", "includes_products": false, "includes_recent_news": false, "includes_company_background": false, "includes_market_position": false, "tone": "professional but fabricated", "length": "2 paragraphs", "has_greeting": true, "has_signoff": true, "issues": ["Hallucinated founder names", "Made up previous company affiliations", "All team information is fabricated"]}', 'assertions_result': {'passed': False, 'errors': ['Writer agent created fictional founder and team information when no data was available. This demonstrates dangerous hallucination behavior']}}

---
