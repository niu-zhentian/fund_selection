from datetime import datetime

import akshare as ak
import pandas as pd

# =====================================================
# 获取基金列表
# =====================================================

print("正在获取基金列表...")

fund_list = ak.fund_name_em()

fund_list.to_csv(
    "china_funds.csv",
    index=False,
    encoding="utf-8-sig"
)

# =====================================================
# 只保留股票基金和混合基金,可以根据需要修改基金类型/如果想要比较指定类型基金全部数量，删掉【：200】即可
# =====================================================

fund_list = fund_list[
    fund_list["基金简称"].str.contains(
        "混合|股票",
        na=False
    )
]

selected_fund_codes = (
    fund_list["基金代码"]
    .tolist()[:200]
)

print(
    f"共获取到 {len(selected_fund_codes)} 只基金"
)

# =====================================================
# 参数设置
# =====================================================

starttime = "2024-01-01"
endtime = "2025-12-31"

initial_investment = 10000

monthly_investment = 1000

# 保证与月定投年金额一致
weekly_investment = round(
    monthly_investment * 12 / 52,
    2
)

# =====================================================
# 基金名称
# =====================================================

def find_fund_name(fund_code):

    fund_info = fund_list[
        fund_list["基金代码"] == fund_code
    ]

    if not fund_info.empty:
        return fund_info.iloc[0]["基金简称"]

    return "未知基金"


# =====================================================
# 获取基金历史净值
# =====================================================

def get_fund_data(fund_code):

    try:

        hist_data = ak.fund_open_fund_info_em(
            symbol=fund_code,
            indicator="单位净值走势"
        )

        if hist_data.empty:
            return None

        if "净值日期" not in hist_data.columns:
            return None

        hist_data["净值日期"] = pd.to_datetime(
            hist_data["净值日期"]
        )

        hist_data["单位净值"] = pd.to_numeric(
            hist_data["单位净值"],
            errors="coerce"
        )

        hist_data = (
            hist_data
            .dropna()
            .set_index("净值日期")
        )

        return hist_data

    except Exception as e:

        print(
            f"获取基金 {fund_code} 数据失败：{e}"
        )

        return None


# =====================================================
# 回测
# =====================================================

def backtest(
        hist_data,
        start_date,
        end_date,
        initial_investment,
        periodic_investment,
        freq):

    data = hist_data.copy()

    data = data[
        (data.index >= pd.to_datetime(start_date))
        &
        (data.index <= pd.to_datetime(end_date))
    ]

    if data.empty:
        return None

    first_nav = data.iloc[0]["单位净值"]

    total_investment = initial_investment

    fund_units = (
        initial_investment / first_nav
    )

    records = [{
        "Date": data.index[0],
        "Portfolio Value":
            fund_units * first_nav,
        "Total Investment":
            total_investment
    }]

    invest_dates = pd.date_range(
        start=start_date,
        end=end_date,
        freq=freq
    )

    for date in invest_dates:

        closest_date = data.index.asof(date)

        if pd.isna(closest_date):
            continue

        nav = data.loc[
            closest_date,
            "单位净值"
        ]

        fund_units += (
            periodic_investment / nav
        )

        total_investment += (
            periodic_investment
        )

        portfolio_value = (
            fund_units * nav
        )

        records.append({
            "Date": closest_date,
            "Portfolio Value":
                portfolio_value,
            "Total Investment":
                total_investment
        })

    result_df = pd.DataFrame(records)

    result_df["Net Value"] = (
        result_df["Portfolio Value"]
        -
        result_df["Total Investment"]
    )

    result_df["Return"] = (
        result_df["Net Value"]
        /
        result_df["Total Investment"]
    )

    result_df["Drawdown"] = (
        1
        -
        result_df["Portfolio Value"]
        /
        result_df["Portfolio Value"].cummax()
    )

    return result_df


# =====================================================
# 统计指标
# =====================================================

def calc_statistics(
        hist_data,
        result_df,
        start_date,
        end_date,
        initial_investment,
        periodic_investment,
        freq):

    total_investment = (
        result_df["Total Investment"]
        .iloc[-1]
    )

    final_value = (
        result_df["Portfolio Value"]
        .iloc[-1]
    )

    profit = (
        final_value
        -
        total_investment
    )

    final_return = (
        profit
        /
        total_investment
    )

    years = (
        pd.to_datetime(end_date)
        -
        pd.to_datetime(start_date)
    ).days / 365.25

    annual_return = (
        (
            final_value
            /
            total_investment
        ) **
        (1 / years)
        -
        1
    )

    # ===============================
    # 真实账户价值曲线
    # ===============================

    data = hist_data.copy()

    data = data[
        (data.index >= pd.to_datetime(start_date))
        &
        (data.index <= pd.to_datetime(end_date))
    ]

    invest_dates = pd.date_range(
        start=start_date,
        end=end_date,
        freq=freq
    )

    total_units = 0

    first_nav = data.iloc[0]["单位净值"]

    total_units += (
        initial_investment
        / first_nav
    )

    buy_records = []

    buy_records.append(
        (
            data.index[0],
            initial_investment
        )
    )

    for date in invest_dates:

        closest_date = data.index.asof(date)

        if pd.isna(closest_date):
            continue

        buy_records.append(
            (
                closest_date,
                periodic_investment
            )
        )

    buy_records.sort(
        key=lambda x: x[0]
    )

    units = 0

    daily_values = []

    buy_index = 0

    for current_date, row in data.iterrows():

        while (
            buy_index < len(buy_records)
            and
            buy_records[buy_index][0]
            <= current_date
        ):

            invest_money = (
                buy_records[buy_index][1]
            )

            nav = data.loc[
                buy_records[buy_index][0],
                "单位净值"
            ]

            units += (
                invest_money / nav
            )

            buy_index += 1

        asset_value = (
            units
            *
            row["单位净值"]
        )

        daily_values.append(
            asset_value
        )

    daily_value_series = pd.Series(
        daily_values,
        index=data.index
    )

    drawdown = (
        daily_value_series
        /
        daily_value_series.cummax()
        -
        1
    )

    max_drawdown = abs(
        drawdown.min()
    )

    # 防止除零
    max_drawdown = max(
        max_drawdown,
        0.001
    )

    calmar_ratio = (
        annual_return
        /
        max_drawdown
    )

    return {

        "最终净值":
            round(final_value, 2),

        "总投资金额":
            round(total_investment, 2),

        "盈利金额":
            round(profit, 2),

        "收益率":
            round(final_return, 4),

        "年化收益率":
            round(annual_return, 4),

        "最大回撤":
            round(max_drawdown, 4),

        "卡玛比率":
            round(calmar_ratio, 4)
    }


# =====================================================
# 开始回测
# =====================================================

stats = []

failed_funds = []

total_count = len(
    selected_fund_codes
)

for i, fund_code in enumerate(
        selected_fund_codes):

    print(
        f"[{i+1}/{total_count}] "
        f"{fund_code}"
    )

    hist_data = get_fund_data(
        fund_code
    )

    if hist_data is None:

        failed_funds.append(
            fund_code
        )

        continue

    try:

        month_result = backtest(
            hist_data,
            starttime,
            endtime,
            initial_investment,
            monthly_investment,
            "ME"
        )

        week_result = backtest(
            hist_data,
            starttime,
            endtime,
            initial_investment,
            weekly_investment,
            "W"
        )

        if month_result is None:
            continue

        if week_result is None:
            continue

        month_stat = (
            calc_statistics(
                hist_data,
                month_result,
                starttime,
                endtime,
                initial_investment,
                monthly_investment,
                "ME"
            )
        )

        week_stat = (
            calc_statistics(
                hist_data,
                week_result,
                starttime,
                endtime,
                initial_investment,
                weekly_investment,
                "W"
            )
        )

        # score = (
        #     week_stat["年化收益率"] * 100
        #     +
        #     (
        #         week_stat["收益率"]
        #         -
        #         month_stat["收益率"]
        #     ) * 50
        #     -
        #     week_stat["最大回撤"] * 100
        # )

        stats.append({

            "基金名称":
                find_fund_name(
                    fund_code
                ),

            "基金代码":
                fund_code,

            "月定投收益率":
                month_stat["收益率"],

            "月定投年化":
                month_stat["年化收益率"],

            "月定投最大回撤":
                month_stat["最大回撤"],

            "月定投卡玛":
                month_stat["卡玛比率"],

            "月定投最终净值":
                month_stat["最终净值"],

            "周定投收益率":
                week_stat["收益率"],

            "周定投年化":
                week_stat["年化收益率"],

            "周定投最大回撤":
                week_stat["最大回撤"],

            "周定投卡玛":
                week_stat["卡玛比率"],

            "周定投最终净值":
                week_stat["最终净值"],

            "周定投收益提升":
                round(
                    week_stat["收益率"]
                    -
                    month_stat["收益率"],
                    4
                ),

            # "综合评分":
            #     round(score, 4)
        })

    except Exception as e:

        print(
            f"回测失败: "
            f"{fund_code}"
        )

        print(e)

        failed_funds.append(
            fund_code
        )

# =====================================================
# 结果
# =====================================================

stats_df = pd.DataFrame(stats)

if stats_df.empty:

    print("没有成功回测的数据")

    exit()

stats_df = stats_df.sort_values(
        by=[
        "周定投卡玛",
        "周定投最终净值"
        ],
        ascending=[
            False,
            False
    ]
)

best_funds = stats_df.head(20)

# =====================================================
# 导出HTML
# =====================================================

timestamp = datetime.now().strftime(
    "%Y%m%d-%H%M%S"
)

html_file_name = (
    f"backtest_stats_{timestamp}.html"
)

with open(
    html_file_name,
    "w",
    encoding="utf-8"
) as f:

    f.write(
        "<h1>基金定投回测结果</h1>"
    )

    f.write(
        f"<h3>{starttime} -> {endtime}</h3>"
    )

    f.write(
        f"<p>股票+混合基金数量："
        f"{len(selected_fund_codes)}</p>"
    )

    f.write(
        f"<p>成功回测："
        f"{len(stats)}</p>"
    )

    f.write(
        f"<p>失败数量："
        f"{len(failed_funds)}</p>"
    )

    f.write(
        f"<p>月定投金额："
        f"{monthly_investment}</p>"
    )

    f.write(
        f"<p>周定投金额："
        f"{weekly_investment}</p>"
    )

    f.write("<hr>")

    f.write(
        "<h2>周定投卡玛TOP20</h2>"
    )

    f.write(
        best_funds.to_html(
            index=False
        )
    )

    f.write("<br><br>")

    f.write(
        "<h2>全部结果</h2>"
    )

    f.write(
        stats_df.to_html(
            index=False
        )
    )

print(
    f"\n结果已保存到: {html_file_name}"
)

print(
    f"成功: {len(stats)}"
)

print(
    f"失败: {len(failed_funds)}"
)

print("\nTOP10基金:")

print(
    stats_df.head(10)[[
        "基金名称",
        "基金代码",
        "周定投收益率",
        "周定投年化",
        "综合评分"
    ]]
)