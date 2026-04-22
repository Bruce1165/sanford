            'market_cap': stock_info.get('market_cap'),
            'circulating_cap': stock_info.get('circulating_cap'),
            'is_positive': is_positive,
            'first_trigger_date': first_trigger_date,
            'first_trigger_screener': first_trigger_screener,
            'screener_triggers': triggers
        })

    conn.close()

    logger.info(f"Dataset built: {len(records)} records")
    logger.info(f"Positive cases: {sum(1 for r in records if r['is_positive'])}")
    logger.info(f"Negative cases: {sum(1 for r in records if not r['is_positive'])}")

    # Save to CSV
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = OUTPUT_DIR / f'ground_truth_dataset_{timestamp}.csv'

    columns = [
        'code', 'name', 'industry', 'market_cap', 'circulating_cap',
