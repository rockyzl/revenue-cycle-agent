# 先把它当成一个医院财务收件箱

患者在医院网站登录，选中自己的账单，问：“保险已经付了，为什么我还欠钱？”工作人员通常要查账单、保险处理结果和付款记录，再回复。这个 demo 就演示这段工作。

[打开 Demo](https://revenue-cycle-agent-1038659864130.us-central1.run.app)

## 三分钟怎么演示

1. 点击 **Anna → Use this demo account**。选第一张账单，保险已付 $700，当前余额 $300。
2. 点击 **Send question**。这里是患者发消息的入口，不是 AI 自己制造问题。
3. 点击 **Switch account**，用 **Financial reviewer（财务审核员）** 登录。等草稿出现，展开“View tool calls and evidence”。
4. 读草稿并修改，然后点 **Approve reply**。这个按钮实际完成 UiPath Action Center 的审核任务，Maestro 收到结果后继续运行。
5. 再换回 Anna，才能看到审核后的回复。想演示失败分支，用 Ben 的“Possible duplicate lab charge”问题，审核员点击拒绝；患者不会收到 AI 草稿。
6. 点“Try accessing another patient’s bill”，系统会拒绝。Anna 的家属账单有单独授权，因此可以查看。

整个演示都在同一个网页完成，不需要另行登录 UiPath 后台。看到“Waiting for staff review”，就表示草稿在等财务审核员批准。真实医院里患者和审核员是两个人；这个 demo 让你切换账户体验两种角色。

## 用一件事记住各工具

| 工具 | 在这个例子里干什么 |
|---|---|
| Identity Platform | 检查账号是否登录成功 |
| Firestore 数据库 + 服务端授权代码 | 查这个账号对应谁、是否有权查看选中的账单 |
| LangGraph | 组织 agent 的工具调用、草稿和证据核对步骤 |
| Vertex AI / Gemini | 理解患者问题，选择工具，组织解释 |
| UiPath Maestro | 启动 agent，派审核任务，等待，再根据审核结果继续 |
| UiPath Action Center | 存放需要人决定的审核任务 |
| FastAPI / Cloud Run | 提供网页与 API，执行后台程序 |

**Agent 处理“这个问题该查什么、怎么解释”；Maestro 管“这件事现在到哪一步、该等谁、接下来做什么”。** 两者都有流程编排能力。这是项目中的分工，不是绝对的产品能力边界。

UiPath 是一个自动化平台，Maestro 是其中的流程编排产品。它不是保存客户资料的 CRM。传统 RPA 机器人可以在没有 API 的旧系统里点击、填表；本 demo 的系统有 API，所以没有部署桌面机器人。不要在面试时说做了 Studio 机器人、Document Understanding 或 AI Center。

## 怎么知道问问题的人能看这张账单

登录成功的令牌包含由身份服务签发的 issuer + subject。后台验证令牌，再查预先建立的账户映射与患者授权。每次查账单和保险事件都重新检查权限，**不会因为问题里写了某人的姓名，就认定他是那个人**。模型也拿不到任意患者查询工具。

现实医院还需要真正的患者身份核验、开户与家属代理授权制度。本项目只有公开的虚构演示账户，尚未接入医院 SSO；数据库是身份映射和权限数据的存放处，本身不是 SSO。

## 数据哪些是真的

- 登录服务、Firestore 数据库、Vertex AI 推理、Maestro 运行和 Action Center 审核任务：真实云服务。
- Anna、Ben、家属、个人账单、保险处理事件、付款记录：明确虚构的演示数据，不是 Mayo 的患者。
- CMS 页面：真实的官方医院历史平均费用，独立于患者流程。CMS 是美国医疗保险和医疗补助服务中心，不是患者账单系统。

例如 Anna 的账单中保险已付 $700，患者责任是 $300（$200 deductible + $100 coinsurance）。这是按演示账单记录解释；绝不能拿 CMS 的两个医院平均值相减，当成个人欠款。

## 和 Mayo 岗位怎么联系

岗位明确提到 patient portal inbasket management：处理患者门户里积压的消息。这个原型展示了“已登录患者消息 → 有权限的数据查询 → AI 草稿 → 人工审核 → 返回消息”的参考流程，和该任务直接相关。

它证明的是一个可运行的独立原型和具体架构选择，不是多年医院生产系统经验。面试时可以直接说：**“我的实际工作强项是 AI agent、Azure 应用交付，以及保险建模与验证。UiPath/GCP 是我为理解这个场景做的独立项目，我可以展示实际运行和边界。”**


英文界面更新：页面、示例问题、新生成的 AI 草稿和审核表单使用英文；已移除访客不需要的 UiPath 后台登录入口及展开式面试说明。既有演示咨询、草稿和证据也以英文显示，数据库保留原始记录。
