import React, {useEffect, useState} from "react";
import Button from "@material-ui/core/Button";
import {unlockTallySheet} from "../../services/tabulation-api";
import {MESSAGES_EN} from "../../locale/messages_en";
import {MESSAGE_TYPES} from "../../services/messages.provider";

export default function UnlockButton(props) {
    const {fetchHtml} = props;

    const {children, onProcessing, tallySheet, setTallySheet} = props;
    const [processing, setProcessing] = useState(false);

    const {tallySheetId} = tallySheet;

    useEffect(() => {
        onProcessing && onProcessing(processing);
    }, [processing])

    const handleOnClick = () => async (event) => {
        setProcessing(true);
        try {
            const tallySheet = await unlockTallySheet(tallySheetId);
            await setTallySheet(tallySheet);
            messages.push("Success", MESSAGES_EN.success_report_unlock, MESSAGE_TYPES.SUCCESS);
            setTimeout(() => {
                history.push(getTallySheetListLink())
            }, 500)
        } catch (e) {
            messages.push("Error", MESSAGES_EN.error_unlock_report, MESSAGE_TYPES.ERROR);
        }
        setProcessing(false);
    };

    return <Button
        variant={props.variant}
        color={props.color}
        size={props.size}
        disabled={processing}
        onClick={handleOnClick()}
    >
        {children}
    </Button>
}
